// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {ImpermanentLossHedgingVault} from "../src/ImpermanentLossHedgingVault.sol";
import {MockERC20} from "../src/mocks/MockERC20.sol";
import {MockWETH9} from "../src/mocks/MockWETH9.sol";
import {MockOracle} from "../src/mocks/MockOracle.sol";
import {MockUniswapV2Pair} from "../src/mocks/MockUniswapV2Pair.sol";
import {MockUniswapV2Router02} from "../src/mocks/MockUniswapV2Router02.sol";
import {MockAavePool} from "../src/mocks/MockAavePool.sol";

contract VaultAccountingTest is Test {
    MockERC20 internal usdc;
    MockWETH9 internal weth;
    MockOracle internal oracle;
    MockUniswapV2Pair internal pair;
    MockUniswapV2Router02 internal router;
    MockAavePool internal pool;
    ImpermanentLossHedgingVault internal vault;

    address internal constant USER = address(0xBEEF);
    uint256 internal constant INITIAL_ETH = 1 ether;
    uint256 internal constant INITIAL_USDC = 2_000e6;

    function setUp() public {
        usdc = new MockERC20("USD Coin", "USDC", 6);
        weth = new MockWETH9();
        router = new MockUniswapV2Router02(address(weth), address(usdc));
        pair = new MockUniswapV2Pair(address(weth), address(usdc), address(router));
        router.setPair(address(pair));
        oracle = new MockOracle(2_000e8, 8, "ETH / USD");
        pool = new MockAavePool(address(weth));

        vault = new ImpermanentLossHedgingVault(
            address(this),
            address(router),
            address(pair),
            address(pool),
            address(oracle),
            address(usdc),
            address(weth),
            6
        );

        deal(USER, INITIAL_ETH);
        deal(address(usdc), USER, INITIAL_USDC);
        deal(address(usdc), address(router), 10_000_000e6);
        deal(address(weth), address(router), 10_000 ether);
        deal(address(weth), address(pool), 10_000 ether);

        vm.prank(USER);
        usdc.approve(address(vault), type(uint256).max);

        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);
    }

    function testCurrentDeltaPositiveAfterDeposit() public {
        assertGt(vault.getCurrentDelta(), 0);
    }

    function testCurrentDebtPositiveAfterDeposit() public {
        assertGt(vault.getCurrentDebt(), 0);
    }

    function testCapitalPositionIncludesLpAssetAndDebt() public {
        (uint256 lpAssetValue, uint256 debtValue, int256 netAssetValue) = vault.getCapitalPosition1e18();

        assertGt(lpAssetValue, 0, "LP asset value should be positive");
        assertGt(debtValue, 0, "debt value should be positive");
        assertGt(netAssetValue, 0, "net asset value should be positive after safe deposit");
    }

    function testHealthFactorPositive() public {
        assertGt(vault.getHealthFactorBps(), 0);
    }

    function testImpermanentLossNearZeroAtEntry() public {
        int256 il = vault.getImpermanentLoss();
        int256 absIl = il >= 0 ? il : -il;

        // Allow small rounding noise in 1e18 scale.
        assertLe(uint256(absIl), 1e14);
    }

    function testDebtAccruesOverTimeWhenBorrowRatePositive() public {
        uint256 debtBefore = vault.getCurrentDebt();

        vm.warp(block.timestamp + 30 days);

        uint256 debtAfter = vault.getCurrentDebt();
        assertGt(debtAfter, debtBefore, "debt should accrue over time");
    }
}
