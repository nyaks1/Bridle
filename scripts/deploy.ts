import hre from "hardhat";
import { ethers, ContractFactory } from "ethers";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main(): Promise<void> {
  const networkArgIdx = process.argv.indexOf("--network");
  const selectedNetwork = networkArgIdx !== -1 ? process.argv[networkArgIdx + 1] : "hedera_testnet";

  console.log(`--> Connected to network: ${selectedNetwork}`);

  const networks = (hre.config as any)?.networks || {};
  const networkConfig = networks[selectedNetwork] || {};

  // Ensure rpcUrl is strictly a primitive string
  const rawUrl = process.env.HEDERA_RPC_URL || networkConfig.url || "https://testnet.hashio.io/api";
  const rpcUrl = String(rawUrl).trim();

  // Ensure private key is strictly a primitive string
  let rawKey: any = process.env.OPERATOR_PRIVATE_KEY;
  if (!rawKey && networkConfig.accounts) {
    const firstAcc = networkConfig.accounts[0];
    rawKey = typeof firstAcc === "string" ? firstAcc : firstAcc?.privateKey;
  }

  if (!rawKey) {
    throw new Error("No private key configured. Check OPERATOR_PRIVATE_KEY in .env");
  }

  const cleanKey = String(rawKey).trim();
  const privateKey = cleanKey.startsWith("0x") ? cleanKey : `0x${cleanKey}`;

  // Pass primitive string URL to JsonRpcProvider
  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const signer = new ethers.Wallet(privateKey, provider);

  console.log(`Deployer address: ${signer.address}`);

  const balance = await provider.getBalance(signer.address);
  console.log(`Account balance: ${ethers.formatEther(balance)} HBAR`);

  // Load contract artifact
  const artifactPath = path.resolve(__dirname, "../artifacts/contracts/BridlePaywall.sol/BridlePaywall.json");
  if (!fs.existsSync(artifactPath)) {
    throw new Error("Artifact not found. Run 'npx hardhat compile' first.");
  }
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf-8"));

  console.log("Broadcasting BridlePaywall deployment transaction...");
  const factory = new ContractFactory(artifact.abi, artifact.bytecode, signer);
  const paywall = await factory.deploy();

  console.log(`Transaction Hash: ${paywall.deploymentTransaction()?.hash}`);
  console.log("Waiting for confirmation on Hedera Testnet...");

  await paywall.waitForDeployment();
  const contractAddress = await paywall.getAddress();

  console.log("----------------------------------------------------------------");
  console.log(`BridlePaywall deployed successfully to: ${contractAddress}`);
  console.log(`HashScan: https://hashscan.io/testnet/address/${contractAddress}`);
  console.log("----------------------------------------------------------------");
}

main().catch((error: unknown) => {
  console.error("Deployment failed:", error);
  process.exit(1);
});