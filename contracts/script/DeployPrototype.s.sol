// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";

import {ImpermanentLossHedgingVault} from "../src/ImpermanentLossHedgingVault.sol";
import {MockERC20} from "../src/mocks/MockERC20.sol";
import {MockWETH9} from "../src/mocks/MockWETH9.sol";
import {MockOracle} from "../src/mocks/MockOracle.sol";
import {MockUniswapV2Pair} from "../src/mocks/MockUniswapV2Pair.sol";
import {MockUniswapV2Router02} from "../src/mocks/MockUniswapV2Router02.sol";
import {MockAavePool} from "../src/mocks/MockAavePool.sol";

contract DeployPrototype is Script {
    struct Deployment {
        address usdc;
        address weth;
        address router;
        address pair;
        address oracle;
        address aavePool;
        address vault;
    }

    event PrototypeDeployed(
        address indexed deployer,
        address usdc,
        address weth,
        address router,
        address pair,
        address oracle,
        address aavePool,
        address vault
    );

    function run() external returns (Deployment memory deployment) {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

        MockERC20 usdc = new MockERC20("Mock USD Coin", "mUSDC", 6);
        MockWETH9 weth = new MockWETH9();

        MockUniswapV2Router02 router = new MockUniswapV2Router02(
            address(weth),
            address(usdc)
        );

        MockUniswapV2Pair pair = new MockUniswapV2Pair(
            address(weth),
            address(usdc),
            address(router)
        );

        router.setPair(address(pair));

        MockOracle oracle = new MockOracle(
            2_000e8,
            8,
            "ETH / USD"
        );

        MockAavePool aavePool = new MockAavePool(address(weth));

        ImpermanentLossHedgingVault vault = new ImpermanentLossHedgingVault(
            msg.sender,
            address(router),
            address(pair),
            address(aavePool),
            address(oracle),
            address(usdc),
            address(weth),
            6
        );

        // Demo balances for local/Sepolia prototype interactions.
        usdc.mint(msg.sender, 1_000_000e6);
        usdc.mint(address(router), 10_000_000e6);

        weth.mint(address(router), 10_000 ether);
        weth.mint(address(aavePool), 10_000 ether);

        deployment = Deployment({
            usdc: address(usdc),
            weth: address(weth),
            router: address(router),
            pair: address(pair),
            oracle: address(oracle),
            aavePool: address(aavePool),
            vault: address(vault)
        });

        emit PrototypeDeployed(
            msg.sender,
            address(usdc),
            address(weth),
            address(router),
            address(pair),
            address(oracle),
            address(aavePool),
            address(vault)
        );

        vm.stopBroadcast();

        return deployment;
    }
}