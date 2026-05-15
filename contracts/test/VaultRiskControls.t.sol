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

contract VaultRiskControlsTest is Test {
    MockERC20 internal usdc;
    MockWETH9 internal weth;
    MockOracle internal oracle;
    MockUniswapV2Pair internal pair;
    MockUniswapV2Router02 internal router;
    MockAavePool internal pool;
    ImpermanentLossHedgingVault internal vault;

    address internal constant USER = address(0xBEEF);
    address internal constant NOT_OWNER = address(0xBAD);
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
    }

    function _deposit() internal {
        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);
    }

    function testOnlyOwnerCanSetRiskParams() public {
        vm.prank(NOT_OWNER);
        vm.expectRevert();
        vault.setRiskParams(100, 100, 20);
    }

    function testOnlyOwnerCanPause() public {
        vm.prank(NOT_OWNER);
        vm.expectRevert();
        vault.pause();
    }

    function testCircuitBreakerBlocksRebalanceWhenOracleDeviationHigh() public {
        _deposit();

        // Pool price remains near 2000, oracle jumps to 4000.
        oracle.setAnswer(4_000e8);

        vm.expectRevert();
        vault.rebalance();
    }

    function testBorrowCapCanBlockDepositOrRebalance() public {
        vault.setCreditRiskParams(
            6_000,
            8_000,
            11_000,
            0.01 ether,
            300
        );

        vm.prank(USER);
        vm.expectRevert();
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);
    }

    function testSlippageParamUpperBoundIsEnforced() public {
        vm.expectRevert();
        vault.setRiskParams(100, 2_001, 20);
    }

    function testThresholdUpperBoundIsEnforced() public {
        vm.expectRevert();
        vault.setRiskParams(5_001, 100, 20);
    }

    function testPauseAndUnpause() public {
        vault.pause();

        vm.prank(USER);
        vm.expectRevert();
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);

        vault.unpause();

        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);

        assertGt(vault.sharesOf(USER), 0);
    }

    function testHealthFactorIsAboveMinimumAfterDeposit() public {
        _deposit();
        assertGt(vault.getHealthFactorBps(), vault.minHealthFactorBps());
    }
}
