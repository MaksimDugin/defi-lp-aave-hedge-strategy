// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockOracle {
    int256 private answer_;
    uint8 public immutable decimals;
    string public description;

    constructor(int256 answer, uint8 decimals_, string memory description_) {
        answer_ = answer;
        decimals = decimals_;
        description = description_;
    }

    function setAnswer(int256 answer) external {
        answer_ = answer;
    }

    function latestAnswer() external view returns (int256) {
        return answer_;
    }

    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        return (1, answer_, block.timestamp, block.timestamp, 1);
    }
}