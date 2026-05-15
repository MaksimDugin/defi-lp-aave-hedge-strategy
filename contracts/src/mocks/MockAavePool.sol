// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {MockWETH9} from "./MockWETH9.sol";

contract MockAavePool {
    address public immutable weth;

    mapping(address => uint256) public debtPrincipal;
    mapping(address => uint256) public lastAccrualTimestamp;

    uint256 public variableBorrowRateBps = 300; // 3% annual

    constructor(address weth_) {
        weth = weth_;
    }

    function setVariableBorrowRateBps(uint256 rateBps) external {
        variableBorrowRateBps = rateBps;
    }

    function borrow(address asset, uint256 amount, address onBehalfOf) external {
        require(asset == weth, "AAVE: only WETH");

        _accrue(onBehalfOf);

        debtPrincipal[onBehalfOf] += amount;

        MockWETH9(payable(weth)).transfer(onBehalfOf, amount);
    }

    function repay(address asset, uint256 amount, address onBehalfOf) external returns (uint256) {
        require(asset == weth, "AAVE: only WETH");

        _accrue(onBehalfOf);

        uint256 debt = debtPrincipal[onBehalfOf];
        uint256 repayAmount = amount > debt ? debt : amount;

        if (repayAmount > 0) {
            MockWETH9(payable(weth)).transferFrom(msg.sender, address(this), repayAmount);
            debtPrincipal[onBehalfOf] = debt - repayAmount;
        }

        return repayAmount;
    }

    function getDebt(address user) external view returns (uint256) {
        uint256 principal = debtPrincipal[user];

        if (principal == 0) {
            return 0;
        }

        uint256 elapsed = block.timestamp - lastAccrualTimestamp[user];
        uint256 interest = principal * variableBorrowRateBps * elapsed / 10_000 / 365 days;

        return principal + interest;
    }

    function _accrue(address user) internal {
        uint256 principal = debtPrincipal[user];

        if (lastAccrualTimestamp[user] == 0) {
            lastAccrualTimestamp[user] = block.timestamp;
            return;
        }

        if (principal == 0) {
            lastAccrualTimestamp[user] = block.timestamp;
            return;
        }

        uint256 elapsed = block.timestamp - lastAccrualTimestamp[user];
        uint256 interest = principal * variableBorrowRateBps * elapsed / 10_000 / 365 days;

        debtPrincipal[user] = principal + interest;
        lastAccrualTimestamp[user] = block.timestamp;
    }
}