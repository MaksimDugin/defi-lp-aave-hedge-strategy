// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockUniswapV2Pair {
    address public immutable token0;
    address public immutable token1;
    address public immutable router;

    uint112 private reserve0;
    uint112 private reserve1;

    constructor(address token0_, address token1_, address router_) {
        token0 = token0_;
        token1 = token1_;
        router = router_;

        // Initial pool price: 1 WETH = 2,000 USDC.
        reserve0 = uint112(1_000 ether);
        reserve1 = uint112(2_000_000e6);
    }

    function setReserves(uint112 reserve0_, uint112 reserve1_) external {
        require(msg.sender == router, "PAIR: only router");
        reserve0 = reserve0_;
        reserve1 = reserve1_;
    }

    function getReserves()
        external
        view
        returns (uint112 reserve0_, uint112 reserve1_, uint32 blockTimestampLast)
    {
        return (reserve0, reserve1, uint32(block.timestamp));
    }

    function priceUsd6() external view returns (uint256) {
        if (reserve0 == 0) {
            return 0;
        }

        // token0 is WETH, token1 is USDC.
        return uint256(reserve1) * 1e18 / uint256(reserve0);
    }
}