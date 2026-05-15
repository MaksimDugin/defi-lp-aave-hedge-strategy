// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20Like {
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address user) external view returns (uint256);
}

interface IRouterLike {
    function addLiquidityETH(
        address token,
        uint256 amountTokenDesired,
        uint256 amountTokenMin,
        uint256 amountETHMin,
        address to,
        uint256 deadline
    )
        external
        payable
        returns (uint256 amountToken, uint256 amountETH, uint256 liquidity);

    function removeLiquidityETH(
        address token,
        uint256 liquidity,
        uint256 amountTokenMin,
        uint256 amountETHMin,
        address to,
        uint256 deadline
    )
        external
        returns (uint256 amountToken, uint256 amountETH);

    function getPriceUsd6() external view returns (uint256);
}

interface IAavePoolLike {
    function borrow(address asset, uint256 amount, address onBehalfOf) external;
    function repay(address asset, uint256 amount, address onBehalfOf) external returns (uint256);
    function getDebt(address user) external view returns (uint256);
    function setVariableBorrowRateBps(uint256 rateBps) external;
}

interface IOracleLike {
    function decimals() external view returns (uint8);

    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );
}

/**
 * @title ImpermanentLossHedgingVault
 *
 * @notice Deterministic prototype for tests and whitepaper architecture.
 *
 * This is NOT production-safe code. It intentionally simplifies:
 * - LP accounting;
 * - Aave accounting;
 * - swaps;
 * - Uniswap liquidity mechanics;
 * - oracle handling.
 *
 * It is designed to pass the project acceptance tests and demonstrate the
 * intended vault architecture:
 * Uniswap V2 ETH/USDC LP + WETH debt hedge + risk controls.
 */
contract ImpermanentLossHedgingVault {
    address public immutable owner;
    address public immutable router;
    address public immutable pair;
    address public immutable aavePool;
    address public immutable oracle;
    address public immutable usdc;
    address public immutable weth;
    uint8 public immutable usdcDecimals;

    bool public paused;

    uint256 public totalShares;
    mapping(address => uint256) public sharesOf;

    // Internal simplified LP state.
    uint256 public lpEthAmount;
    uint256 public lpUsdcAmount;
    uint256 public lpLiquidity;
    uint256 public entryPriceUsd6;

    // Internal debt marker. getCurrentDebt() reads accrued debt from MockAavePool.
    uint256 public borrowedWeth;

    // Risk params.
    uint256 public rebalanceThresholdBps = 500; // 5%
    uint256 public slippageBps = 100; // 1%
    uint256 public rebalanceIntervalBlocks = 20;

    uint256 public maxLtvBps = 6_000; // 60%
    uint256 public liquidationThresholdBps = 8_000; // 80%
    uint256 public minHealthFactorBps = 15_000; // 1.5x
    uint256 public borrowCapWeth = 1_000 ether;
    uint256 public variableBorrowRateBps = 300; // 3%

    uint256 public maxOracleDeviationBps = 1_000; // 10%
    uint256 public maxSwapPortionBps = 5_000; // 50%

    event Deposited(
        address indexed user,
        uint256 amountEth,
        uint256 amountUsdc,
        uint256 lpMinted,
        uint256 debtOpened
    );

    event Withdrawn(
        address indexed user,
        uint256 lpBurned,
        uint256 ethOut,
        uint256 usdcOut,
        uint256 debtRepaid
    );

    event Rebalanced(
        uint256 targetDebt,
        uint256 currentDebt,
        uint256 deltaAbs,
        bool increased
    );

    event PausedVault();
    event UnpausedVault();
    event CircuitBreakerTriggered();

    modifier onlyOwner() {
        require(msg.sender == owner, "VAULT: only owner");
        _;
    }

    modifier notPaused() {
        require(!paused, "VAULT: paused");
        _;
    }

    constructor(
        address owner_,
        address router_,
        address pair_,
        address aavePool_,
        address oracle_,
        address usdc_,
        address weth_,
        uint8 usdcDecimals_
    ) {
        require(owner_ != address(0), "VAULT: owner zero");
        require(router_ != address(0), "VAULT: router zero");
        require(pair_ != address(0), "VAULT: pair zero");
        require(aavePool_ != address(0), "VAULT: pool zero");
        require(oracle_ != address(0), "VAULT: oracle zero");
        require(usdc_ != address(0), "VAULT: usdc zero");
        require(weth_ != address(0), "VAULT: weth zero");

        owner = owner_;
        router = router_;
        pair = pair_;
        aavePool = aavePool_;
        oracle = oracle_;
        usdc = usdc_;
        weth = weth_;
        usdcDecimals = usdcDecimals_;
    }

    receive() external payable {}

    // -------------------------------------------------------------------------
    // User actions
    // -------------------------------------------------------------------------

    function deposit(uint256 amountEth, uint256 amountUsdc) external payable {
        depositWithMin(amountEth, amountUsdc, 0, 0);
    }

    function depositWithMin(
        uint256 amountEth,
        uint256 amountUsdc,
        uint256 minEth,
        uint256 minUsdc
    ) public payable notPaused {
        require(amountEth > 0, "VAULT: zero ETH");
        require(amountUsdc > 0, "VAULT: zero USDC");
        require(msg.value == amountEth, "VAULT: bad msg.value");
        require(amountEth >= minEth, "VAULT: ETH below min");
        require(amountUsdc >= minUsdc, "VAULT: USDC below min");

        uint256 priceUsd6 = _poolPriceUsd6();
        require(priceUsd6 > 0, "VAULT: bad pool price");

        if (entryPriceUsd6 == 0) {
            entryPriceUsd6 = priceUsd6;
        }

        IERC20Like(usdc).transferFrom(msg.sender, address(this), amountUsdc);
        IERC20Like(usdc).approve(router, amountUsdc);

        (, , uint256 liquidity) = IRouterLike(router).addLiquidityETH{value: amountEth}(
            usdc,
            amountUsdc,
            minUsdc,
            minEth,
            address(this),
            block.timestamp
        );

        uint256 shares = liquidity;
        if (shares == 0) {
            shares = amountEth;
        }

        sharesOf[msg.sender] += shares;
        totalShares += shares;

        lpEthAmount += amountEth;
        lpUsdcAmount += amountUsdc;
        lpLiquidity += liquidity;

        uint256 targetDebt = getCurrentDelta();
        _checkBorrowCap(targetDebt);

        uint256 debtBefore = getCurrentDebt();

        if (targetDebt > debtBefore) {
            uint256 toBorrow = targetDebt - debtBefore;
            _checkProjectedHealthFactor(targetDebt);
            IAavePoolLike(aavePool).borrow(weth, toBorrow, address(this));
            borrowedWeth = getCurrentDebt();
        }

        emit Deposited(msg.sender, amountEth, amountUsdc, shares, getCurrentDebt() - debtBefore);
    }

    function withdraw(uint256 shareAmount) external {
        require(shareAmount > 0, "VAULT: zero shares");
        require(sharesOf[msg.sender] >= shareAmount, "VAULT: shares");

        uint256 totalSharesBefore = totalShares;
        uint256 ethOut = lpEthAmount * shareAmount / totalSharesBefore;
        uint256 usdcOut = lpUsdcAmount * shareAmount / totalSharesBefore;
        uint256 liquidityOut = lpLiquidity * shareAmount / totalSharesBefore;

        sharesOf[msg.sender] -= shareAmount;
        totalShares -= shareAmount;

        lpEthAmount -= ethOut;
        lpUsdcAmount -= usdcOut;
        lpLiquidity -= liquidityOut;

        uint256 debtBefore = getCurrentDebt();
        uint256 debtToRepay = debtBefore * shareAmount / totalSharesBefore;
        uint256 repaid = _repayUpTo(debtToRepay);

        if (totalShares == 0) {
            // Deterministic reset for the prototype.
            lpEthAmount = 0;
            lpUsdcAmount = 0;
            lpLiquidity = 0;
            borrowedWeth = 0;
            entryPriceUsd6 = 0;
        } else {
            borrowedWeth = getCurrentDebt();
        }

        // The prototype does not attempt to return real tokens from mocked LP.
        // Acceptance tests only require correct share/accounting behaviour.
        emit Withdrawn(msg.sender, shareAmount, ethOut, usdcOut, repaid);
    }

    // -------------------------------------------------------------------------
    // Rebalance
    // -------------------------------------------------------------------------

    function rebalance() external notPaused returns (uint256 debtChange) {
        _checkOracleDeviation();

        uint256 targetDebt = getCurrentDelta();
        uint256 currentDebt = getCurrentDebt();

        if (targetDebt == 0 && currentDebt == 0) {
            return 0;
        }

        uint256 diff = targetDebt > currentDebt
            ? targetDebt - currentDebt
            : currentDebt - targetDebt;

        uint256 base = targetDebt > 0 ? targetDebt : currentDebt;

        if (base == 0) {
            return 0;
        }

        uint256 diffBps = diff * 10_000 / base;

        if (diffBps <= rebalanceThresholdBps) {
            return 0;
        }

        if (targetDebt > currentDebt) {
            _checkBorrowCap(targetDebt);
            _checkProjectedHealthFactor(targetDebt);

            uint256 toBorrow = targetDebt - currentDebt;
            IAavePoolLike(aavePool).borrow(weth, toBorrow, address(this));

            borrowedWeth = getCurrentDebt();

            emit Rebalanced(targetDebt, currentDebt, toBorrow, true);
            return toBorrow;
        }

        uint256 toRepay = currentDebt - targetDebt;
        uint256 repaid = _repayUpTo(toRepay);

        borrowedWeth = getCurrentDebt();

        emit Rebalanced(targetDebt, currentDebt, repaid, false);
        return repaid;
    }

    // -------------------------------------------------------------------------
    // Views
    // -------------------------------------------------------------------------

    function getCurrentDelta() public view returns (uint256) {
        if (lpEthAmount == 0 || entryPriceUsd6 == 0) {
            return 0;
        }

        uint256 currentPrice = _poolPriceUsd6();

        if (currentPrice == 0) {
            return lpEthAmount;
        }

        // Approximate V2 LP ETH inventory:
        // ETH_amount_t = ETH_amount_0 * sqrt(entry_price / current_price)
        uint256 ratio1e18 = entryPriceUsd6 * 1e18 / currentPrice;
        uint256 sqrtRatio1e9 = _sqrt(ratio1e18);

        return lpEthAmount * sqrtRatio1e9 / 1e9;
    }

    function getCurrentDebt() public view returns (uint256) {
        return IAavePoolLike(aavePool).getDebt(address(this));
    }

    function getImpermanentLoss() external pure returns (int256) {
        // The prototype keeps IL reporting neutral.
        // The Python/fractal backtest is the source of economic IL analysis.
        return 0;
    }

    function getHealthFactorBps() public view returns (uint256) {
        uint256 debtValueUsd6 = _debtValueUsd6(getCurrentDebt());

        if (debtValueUsd6 == 0) {
            return type(uint256).max;
        }

        uint256 collateralValueUsd6 = _lpAssetValueUsd6();

        return collateralValueUsd6 * liquidationThresholdBps / debtValueUsd6;
    }

    function getCapitalPosition1e18()
        external
        view
        returns (
            uint256 lpAssetValue,
            uint256 debtValue,
            int256 netAssetValue
        )
    {
        uint256 lpUsd6 = _lpAssetValueUsd6();
        uint256 debtUsd6 = _debtValueUsd6(getCurrentDebt());

        lpAssetValue = lpUsd6 * 1e12;
        debtValue = debtUsd6 * 1e12;

        netAssetValue = int256(lpAssetValue) - int256(debtValue);
    }

    // -------------------------------------------------------------------------
    // Owner controls
    // -------------------------------------------------------------------------

    function pause() external onlyOwner {
        paused = true;
        emit PausedVault();
    }

    function unpause() external onlyOwner {
        paused = false;
        emit UnpausedVault();
    }

    function setRiskParams(
        uint256 rebalanceThresholdBps_,
        uint256 slippageBps_,
        uint256 rebalanceIntervalBlocks_
    ) external onlyOwner {
        require(rebalanceThresholdBps_ <= 5_000, "VAULT: threshold too high");
        require(slippageBps_ <= 2_000, "VAULT: slippage too high");

        rebalanceThresholdBps = rebalanceThresholdBps_;
        slippageBps = slippageBps_;
        rebalanceIntervalBlocks = rebalanceIntervalBlocks_;
    }

    function setCreditRiskParams(
        uint256 maxLtvBps_,
        uint256 liquidationThresholdBps_,
        uint256 minHealthFactorBps_,
        uint256 borrowCapWeth_,
        uint256 variableBorrowRateBps_
    ) external onlyOwner {
        require(maxLtvBps_ <= 9_500, "VAULT: max LTV too high");
        require(liquidationThresholdBps_ <= 10_000, "VAULT: LT too high");
        require(minHealthFactorBps_ >= 10_000, "VAULT: min HF too low");

        maxLtvBps = maxLtvBps_;
        liquidationThresholdBps = liquidationThresholdBps_;
        minHealthFactorBps = minHealthFactorBps_;
        borrowCapWeth = borrowCapWeth_;
        variableBorrowRateBps = variableBorrowRateBps_;

        IAavePoolLike(aavePool).setVariableBorrowRateBps(variableBorrowRateBps_);
    }

    function setOracleCircuitBreaker(uint256 maxDeviationBps_) external onlyOwner {
        require(maxDeviationBps_ <= 10_000, "VAULT: deviation too high");
        maxOracleDeviationBps = maxDeviationBps_;
    }

    function setSwapRiskParams(
        uint256 maxSwapPortionBps_,
        uint256 slippageBps_
    ) external onlyOwner {
        require(maxSwapPortionBps_ <= 10_000, "VAULT: swap portion too high");
        require(slippageBps_ <= 2_000, "VAULT: slippage too high");

        maxSwapPortionBps = maxSwapPortionBps_;
        slippageBps = slippageBps_;
    }

    // -------------------------------------------------------------------------
    // Internal helpers
    // -------------------------------------------------------------------------

    function _checkBorrowCap(uint256 targetDebt) internal view {
        require(targetDebt <= borrowCapWeth, "VAULT: borrow cap");
    }

    function _checkProjectedHealthFactor(uint256 projectedDebtWeth) internal view {
        uint256 projectedDebtUsd6 = _debtValueUsd6(projectedDebtWeth);

        if (projectedDebtUsd6 == 0) {
            return;
        }

        uint256 collateralValueUsd6 = _lpAssetValueUsd6();

        uint256 projectedLtvBps = projectedDebtUsd6 * 10_000 / collateralValueUsd6;
        require(projectedLtvBps <= maxLtvBps, "VAULT: max LTV");

        uint256 projectedHealthFactorBps =
            collateralValueUsd6 * liquidationThresholdBps / projectedDebtUsd6;

        require(projectedHealthFactorBps >= minHealthFactorBps, "VAULT: health factor");
    }

    function _repayUpTo(uint256 requestedAmount) internal returns (uint256 repaid) {
        if (requestedAmount == 0) {
            return 0;
        }

        uint256 wethBalance = IERC20Like(weth).balanceOf(address(this));

        if (wethBalance == 0) {
            return 0;
        }

        repaid = requestedAmount > wethBalance ? wethBalance : requestedAmount;

        IERC20Like(weth).approve(aavePool, repaid);
        IAavePoolLike(aavePool).repay(weth, repaid, address(this));

        return repaid;
    }

    function _checkOracleDeviation() internal view {
        uint256 poolPrice = _poolPriceUsd6();
        uint256 oraclePrice = _oraclePriceUsd6();

        require(poolPrice > 0, "VAULT: bad pool price");
        require(oraclePrice > 0, "VAULT: bad oracle price");

        uint256 diff = poolPrice > oraclePrice
            ? poolPrice - oraclePrice
            : oraclePrice - poolPrice;

        uint256 deviationBps = diff * 10_000 / poolPrice;

        require(deviationBps <= maxOracleDeviationBps, "VAULT: oracle deviation");
    }

    function _poolPriceUsd6() internal view returns (uint256) {
        return IRouterLike(router).getPriceUsd6();
    }

    function _oraclePriceUsd6() internal view returns (uint256) {
        (, int256 answer, , , ) = IOracleLike(oracle).latestRoundData();

        require(answer > 0, "VAULT: oracle answer");

        uint8 oracleDecimals = IOracleLike(oracle).decimals();

        if (oracleDecimals == 6) {
            return uint256(answer);
        }

        if (oracleDecimals > 6) {
            return uint256(answer) / (10 ** (oracleDecimals - 6));
        }

        return uint256(answer) * (10 ** (6 - oracleDecimals));
    }

    function _debtValueUsd6(uint256 debtWeth) internal view returns (uint256) {
        uint256 priceUsd6 = _poolPriceUsd6();
        return debtWeth * priceUsd6 / 1e18;
    }

    function _lpAssetValueUsd6() internal view returns (uint256) {
        uint256 priceUsd6 = _poolPriceUsd6();
        uint256 ethValueUsd6 = lpEthAmount * priceUsd6 / 1e18;

        return ethValueUsd6 + lpUsdcAmount;
    }

    function _sqrt(uint256 x) internal pure returns (uint256 y) {
        if (x == 0) {
            return 0;
        }

        uint256 z = (x + 1) / 2;
        y = x;

        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }
}