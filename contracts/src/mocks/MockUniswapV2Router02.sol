// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {MockWETH9} from "./MockWETH9.sol";
import {MockERC20} from "./MockERC20.sol";
import {MockUniswapV2Pair} from "./MockUniswapV2Pair.sol";

contract MockUniswapV2Router02 {
    address public immutable weth;
    address public immutable usdc;
    address public pair;

    constructor(address weth_, address usdc_) {
        weth = weth_;
        usdc = usdc_;
    }

    function setPair(address pair_) external {
        pair = pair_;
    }

    function reprice(uint256 priceUsd6) external {
        require(pair != address(0), "ROUTER: pair not set");

        // Keep WETH reserve fixed and adjust USDC reserve.
        uint112 wethReserve = uint112(1_000 ether);
        uint112 usdcReserve = uint112(priceUsd6 * 1_000);

        MockUniswapV2Pair(pair).setReserves(wethReserve, usdcReserve);
    }

    function addLiquidityETH(
        address token,
        uint256 amountTokenDesired,
        uint256,
        uint256,
        address to,
        uint256
    )
        external
        payable
        returns (uint256 amountToken, uint256 amountETH, uint256 liquidity)
    {
        require(token == usdc, "ROUTER: token must be USDC");
        require(pair != address(0), "ROUTER: pair not set");

        MockERC20(usdc).transferFrom(msg.sender, address(this), amountTokenDesired);

        amountToken = amountTokenDesired;
        amountETH = msg.value;

        // Simplified LP token amount in 1e18 scale.
        liquidity = msg.value;

        // Silence unused variable warning.
        to;
    }

    function removeLiquidityETH(
        address token,
        uint256 liquidity,
        uint256,
        uint256,
        address to,
        uint256
    )
        external
        returns (uint256 amountToken, uint256 amountETH)
    {
        require(token == usdc, "ROUTER: token must be USDC");

        amountETH = liquidity;
        amountToken = liquidity * getPriceUsd6() / 1e18;

        MockERC20(usdc).transfer(to, amountToken);

        (bool ok, ) = to.call{value: amountETH}("");
        require(ok, "ROUTER: ETH transfer failed");
    }

    function getPriceUsd6() public view returns (uint256) {
        require(pair != address(0), "ROUTER: pair not set");
        return MockUniswapV2Pair(pair).priceUsd6();
    }

    receive() external payable {}
}