import { expect } from "chai";
import { network } from "hardhat";

const { ethers, networkHelpers } = await network.create();

describe("BridlePaywall", function () {
  async function deployPaywallFixture() {
    const [owner, payer, recipient] = await ethers.getSigners();
    const paywall = await ethers.deployContract("BridlePaywall");
    return { paywall, owner, payer, recipient };
  }

  it("should deploy with the correct owner", async function () {
    const { paywall, owner } = await networkHelpers.loadFixture(deployPaywallFixture);
    expect(await paywall.owner()).to.equal(owner.address);
  });

  it("should accept payment for a service and record it", async function () {
    const { paywall, payer } = await networkHelpers.loadFixture(deployPaywallFixture);
    const serviceId = ethers.keccak256(ethers.toUtf8Bytes("weather_query"));
    const nonce = "nonce-test-123";
    const paymentAmount = ethers.parseEther("0.05");

    await expect(
      paywall.connect(payer).payService(serviceId, nonce, { value: paymentAmount })
    )
      .to.emit(paywall, "PaymentSettled")
      .withArgs(payer.address, serviceId, paymentAmount, nonce, (ts: any) => ts > 0);

    const [paid, amount] = await paywall.hasPaid(payer.address, serviceId, nonce);
    expect(paid).to.be.true;
    expect(amount).to.equal(paymentAmount);
  });

  it("should prevent duplicate nonce replay", async function () {
    const { paywall, payer } = await networkHelpers.loadFixture(deployPaywallFixture);
    const serviceId = ethers.keccak256(ethers.toUtf8Bytes("weather_query"));
    const nonce = "nonce-unique-456";
    const paymentAmount = ethers.parseEther("0.01");

    await paywall.connect(payer).payService(serviceId, nonce, { value: paymentAmount });

    await expect(
      paywall.connect(payer).payService(serviceId, nonce, { value: paymentAmount })
    ).to.be.revertedWithCustomError(paywall, "NonceAlreadyUsed");
  });

  it("should revert if payment value is zero", async function () {
    const { paywall, payer } = await networkHelpers.loadFixture(deployPaywallFixture);
    const serviceId = ethers.keccak256(ethers.toUtf8Bytes("weather_query"));
    const nonce = "nonce-zero-val";

    await expect(
      paywall.connect(payer).payService(serviceId, nonce, { value: 0n })
    ).to.be.revertedWithCustomError(paywall, "InsufficientPayment");
  });

  it("should allow owner to withdraw settled funds", async function () {
    const { paywall, owner, payer, recipient } = await networkHelpers.loadFixture(deployPaywallFixture);
    const serviceId = ethers.keccak256(ethers.toUtf8Bytes("weather_query"));
    const nonce = "nonce-withdraw-789";
    const paymentAmount = ethers.parseEther("1.0");

    await paywall.connect(payer).payService(serviceId, nonce, { value: paymentAmount });

    const balanceBefore = await ethers.provider.getBalance(recipient.address);
    await paywall.connect(owner).withdraw(recipient.address);
    const balanceAfter = await ethers.provider.getBalance(recipient.address);

    expect(balanceAfter - balanceBefore).to.equal(paymentAmount);
  });

  it("should revert if non-owner attempts to withdraw", async function () {
    const { paywall, payer, recipient } = await networkHelpers.loadFixture(deployPaywallFixture);
    await expect(
      paywall.connect(payer).withdraw(recipient.address)
    ).to.be.revertedWithCustomError(paywall, "Unauthorized");
  });
});

