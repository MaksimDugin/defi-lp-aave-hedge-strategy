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

contract VaultDepositWithdrawTest is Test {
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
    }

    function testDepositMintsSharesAndOpensHedgeDebt() public {
        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);

        assertGt(vault.sharesOf(USER), 0, "user should receive vault shares");
        assertGt(vault.totalShares(), 0, "totalShares should increase");
        assertGt(vault.getCurrentDelta(), 0, "LP delta should be positive");
        assertGt(vault.getCurrentDebt(), 0, "hedge debt should be opened");
    }

    function testDepositWithMinMintsShares() public {
        vm.prank(USER);
        vault.depositWithMin{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC, 0, 0);

        assertGt(vault.sharesOf(USER), 0);
        assertGt(vault.getCurrentDelta(), 0);
    }

    function testWithdrawBurnsUserShares() public {
        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);

        uint256 shares = vault.sharesOf(USER);
        assertGt(shares, 0);

        vm.prank(USER);
        vault.withdraw(shares);

        assertEq(vault.sharesOf(USER), 0, "user shares should be burned");
        assertEq(vault.totalShares(), 0, "all shares should be withdrawn");
    }

    function testWithdrawRevertsWhenAmountExceedsShares() public {
        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);

        uint256 shares = vault.sharesOf(USER);

        vm.prank(USER);
        vm.expectRevert();
        vault.withdraw(shares + 1);
    }

    function testDepositRevertsWhenPaused() public {
        vault.pause();

        vm.prank(USER);
        vm.expectRevert();
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);
    }

    function testWithdrawAllowedWhenPaused() public {
        vm.prank(USER);
        vault.deposit{value: INITIAL_ETH}(INITIAL_ETH, INITIAL_USDC);

        uint256 shares = vault.sharesOf(USER);
        vault.pause();

        vm.prank(USER);
        vault.withdraw(shares);

        assertEq(vault.sharesOf(USER), 0);
    }
}
