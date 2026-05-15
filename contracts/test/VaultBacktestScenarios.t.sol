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

contract VaultBacktestScenariosTest is Test {
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

    function _step(uint256 priceUsd6) internal {
        vm.warp(block.timestamp + 1 days);
        vm.roll(block.number + 100);
        router.reprice(priceUsd6);
        oracle.setAnswer(int256(priceUsd6 / 1e6) * 1e8);
        vault.rebalance();
    }

    function testDowntrendScenarioKeepsVaultSolvent() public {
        _step(1_800e6);
        _step(1_500e6);
        _step(1_300e6);

        (uint256 lpAssetValue, uint256 debtValue, int256 netAssetValue) = vault.getCapitalPosition1e18();

        assertGt(lpAssetValue, 0);
        assertGt(debtValue, 0);
        assertGt(netAssetValue, 0, "vault should remain solvent in controlled downtrend");
        assertGt(vault.getHealthFactorBps(), vault.minHealthFactorBps());
    }

    function testHighVolChopScenarioKeepsDebtFinite() public {
        _step(2_300e6);
        _step(1_700e6);
        _step(2_200e6);
        _step(1_900e6);

        assertGt(vault.getCurrentDebt(), 0);
        assertLt(vault.getCurrentDebt(), 10 ether, "debt should remain bounded");
        assertGt(vault.getHealthFactorBps(), vault.minHealthFactorBps());
    }

    function testUserCanExitAfterScenario() public {
        _step(2_300e6);
        _step(1_700e6);
        _step(2_000e6);

        uint256 shares = vault.sharesOf(USER);
        vm.prank(USER);
        vault.withdraw(shares);

        assertEq(vault.sharesOf(USER), 0);
        assertEq(vault.totalShares(), 0);
    }
}
