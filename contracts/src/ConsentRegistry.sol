// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ConsentRegistry
/// @author Angelo David Padilla Romero
/// @notice A tamper-evident registry of patient consent for health-data access.
/// @dev A consent record says: for a (patient, requester, purpose) triple, which
///      categories of data the patient allows (a 16-bit mask) and until when
///      (a Unix expiry). The off-chain service classifies each access request
///      into a purpose and a set of categories and then asks this registry
///      whether consent covers it. No personal or clinical data reaches the
///      chain: patients and requesters are bytes32 ids (hashes), categories are
///      bit positions, and purposes are small codes. Only the operator (the
///      consent-management service, acting on a patient's signed instruction)
///      can grant or revoke, and every change bumps a version and emits an
///      event, so the full consent history is auditable.
contract ConsentRegistry {
    struct Consent {
        uint16 categoryMask; // allowed data categories (bit per category)
        uint64 expiry; // Unix seconds; 0 means no consent on record
        uint32 version; // increments on every grant or revoke
    }

    address public operator;
    uint256 public totalGrants;
    uint256 public totalRevocations;

    // key = keccak256(patient, requester, purpose) -> consent
    mapping(bytes32 => Consent) private _consents;

    event ConsentGranted(
        bytes32 indexed patient,
        bytes32 indexed requester,
        uint8 indexed purpose,
        uint16 categoryMask,
        uint64 expiry,
        uint32 version
    );
    event ConsentRevoked(
        bytes32 indexed patient,
        bytes32 indexed requester,
        uint8 indexed purpose,
        uint32 version
    );
    event OperatorTransferred(address indexed previousOperator, address indexed newOperator);

    error NotOperator();
    error ZeroParty();
    error EmptyScope();
    error PastExpiry();

    modifier onlyOperator() {
        if (msg.sender != operator) revert NotOperator();
        _;
    }

    constructor() {
        operator = msg.sender;
        emit OperatorTransferred(address(0), msg.sender);
    }

    function transferOperator(address newOperator) external onlyOperator {
        if (newOperator == address(0)) revert ZeroParty();
        address previous = operator;
        operator = newOperator;
        emit OperatorTransferred(previous, newOperator);
    }

    function _key(bytes32 patient, bytes32 requester, uint8 purpose)
        private
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(patient, requester, purpose));
    }

    /// @notice Record (or replace) a patient's consent for a requester and purpose.
    /// @param categoryMask the data categories the patient allows (must be non-zero).
    /// @param expiry Unix seconds when the consent lapses (must be in the future).
    function grant(
        bytes32 patient,
        bytes32 requester,
        uint8 purpose,
        uint16 categoryMask,
        uint64 expiry
    ) external onlyOperator returns (uint32 version) {
        if (patient == bytes32(0) || requester == bytes32(0)) revert ZeroParty();
        if (categoryMask == 0) revert EmptyScope();
        if (expiry <= block.timestamp) revert PastExpiry();

        Consent storage c = _consents[_key(patient, requester, purpose)];
        c.categoryMask = categoryMask;
        c.expiry = expiry;
        c.version += 1;
        totalGrants += 1;
        version = c.version;

        emit ConsentGranted(patient, requester, purpose, categoryMask, expiry, version);
    }

    /// @notice Withdraw a patient's consent for a requester and purpose.
    function revoke(bytes32 patient, bytes32 requester, uint8 purpose)
        external
        onlyOperator
        returns (uint32 version)
    {
        Consent storage c = _consents[_key(patient, requester, purpose)];
        c.categoryMask = 0;
        c.expiry = 0;
        c.version += 1;
        totalRevocations += 1;
        version = c.version;

        emit ConsentRevoked(patient, requester, purpose, version);
    }

    /// @notice Read the stored consent for a (patient, requester, purpose) triple.
    function consentOf(bytes32 patient, bytes32 requester, uint8 purpose)
        external
        view
        returns (uint16 categoryMask, uint64 expiry, uint32 version)
    {
        Consent memory c = _consents[_key(patient, requester, purpose)];
        return (c.categoryMask, c.expiry, c.version);
    }

    /// @notice True iff current consent covers every requested category and is
    ///         still valid at the current block time.
    function hasConsent(
        bytes32 patient,
        bytes32 requester,
        uint8 purpose,
        uint16 requiredMask
    ) external view returns (bool) {
        Consent memory c = _consents[_key(patient, requester, purpose)];
        if (c.expiry <= block.timestamp) return false;
        return (c.categoryMask & requiredMask) == requiredMask;
    }
}
