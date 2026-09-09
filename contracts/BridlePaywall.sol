// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract BridlePaywall {
    address public immutable owner;

    mapping(bytes32 => bool) public processedNonces;
    mapping(bytes32 => uint256) public settledPayments;

    event PaymentSettled(
        address indexed payer,
        bytes32 indexed serviceId,
        uint256 amountTinybarOrWei,
        string nonce,
        uint256 timestamp
    );

    error NonceAlreadyUsed();
    error InsufficientPayment();
    error Unauthorized();

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function payService(bytes32 serviceId, string calldata nonce) external payable {
        bytes32 nonceHash = keccak256(abi.encodePacked(nonce));
        if (processedNonces[nonceHash]) revert NonceAlreadyUsed();
        if (msg.value == 0) revert InsufficientPayment();

        processedNonces[nonceHash] = true;
        bytes32 paymentKey = keccak256(abi.encodePacked(msg.sender, serviceId, nonce));
        settledPayments[paymentKey] = msg.value;

        emit PaymentSettled(
            msg.sender,
            serviceId,
            msg.value,
            nonce,
            block.timestamp
        );
    }

    function hasPaid(address payer, bytes32 serviceId, string calldata nonce) external view returns (bool, uint256) {
        bytes32 paymentKey = keccak256(abi.encodePacked(payer, serviceId, nonce));
        uint256 amount = settledPayments[paymentKey];
        return (amount > 0, amount);
    }

    function withdraw(address payable recipient) external onlyOwner {
        uint256 balance = address(this).balance;
        (bool success, ) = recipient.call{value: balance}("");
        require(success, "Withdraw failed");
    }

    receive() external payable {}
}