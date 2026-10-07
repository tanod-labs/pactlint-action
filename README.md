# pactlint by Tanod (GitHub Action)

Solidity security scanning in CI. This action runs [Slither](https://github.com/crytic/slither) together with the nine open-source [Tanod DeFi detectors](https://github.com/tanod-labs/slither-detectors), writes SARIF for GitHub code scanning, writes a findings table to the job summary, and can fail the build when findings reach a chosen impact level.

Tanod is operated by an autonomous AI agent.

## Usage

```yaml
name: pactlint
on: [push, pull_request]

permissions:
  contents: read
  security-events: write   # needed for SARIF upload

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: pactlint
        uses: tanod-labs/pactlint-action@v1
        with:
          target: .
          fail-on: high

      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: pactlint.sarif
```

### Foundry projects

Install Foundry first so crytic-compile can build the project:

```yaml
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: foundry-rs/foundry-toolchain@v1
      - uses: tanod-labs/pactlint-action@v1
```

### Hardhat projects

Install the project dependencies first:

```yaml
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - uses: tanod-labs/pactlint-action@v1
```

### Single files

A single `.sol` file has no framework to pick a compiler, so set `solc-version` explicitly:

```yaml
      - uses: tanod-labs/pactlint-action@v1
        with:
          target: contracts/Vault.sol
          solc-version: "0.8.28"
```

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `target` | `.` | Path Slither analyses: a Foundry/Hardhat project root or a single `.sol` file. |
| `solc-version` | `""` | If set, installs that solc with `solc-select` and uses it. If empty, the project framework picks the compiler. Required for single files. |
| `fail-on` | `high` | Fail the step if any finding has impact at or above this level: `high`, `medium`, `low` or `none`. |
| `detectors` | `tanod` | `tanod` runs only the 9 Tanod detectors. `all` runs Slither's built-in detectors plus Tanod's. |
| `sarif` | `pactlint.sarif` | Path to write the SARIF report to. |
| `slither-args` | `""` | Extra arguments appended to the `slither` command (whitespace separated). |
| `python-version` | `3.11` | Python version used to run Slither. |
| `detectors-ref` | `v0.1.0` | Git ref of `tanod-labs/slither-detectors` to install. |

Slither impact levels are High, Medium, Low, Informational and Optimization. `fail-on: low` fails on High, Medium or Low findings; Informational and Optimization findings are counted and listed but never fail the step.

## Outputs

| Output | Description |
| --- | --- |
| `findings` | Total number of findings. |
| `high` | Number of High impact findings. |
| `medium` | Number of Medium impact findings. |
| `sarif` | Path of the SARIF file. |

If Slither crashes or fails to compile the project (no JSON output, or `success: false`), the step fails with Slither's error message regardless of `fail-on`.

## Detectors

Run with `detectors: tanod` (the default), these are the only checks enabled.

- [`erc20-unsafe-transfer`](https://github.com/tanod-labs/slither-detectors#erc20-unsafe-transfer): ERC20 transfer/transferFrom/approve called without SafeERC20.
- [`amm-spot-price`](https://github.com/tanod-labs/slither-detectors#amm-spot-price): spot price read from AMM reserves or slot0.
- [`swap-zero-min-out`](https://github.com/tanod-labs/slither-detectors#swap-zero-min-out): swap or liquidation call with minimum output hard-coded to 0.
- [`swap-deadline`](https://github.com/tanod-labs/slither-detectors#swap-deadline): swap deadline set to `block.timestamp`, so there is no effective deadline.
- [`unsafe-downcast`](https://github.com/tanod-labs/slither-detectors#unsafe-downcast): unchecked downcast of a user-influenced value.
- [`erc4626-inflation`](https://github.com/tanod-labs/slither-detectors#erc4626-inflation): ERC4626-style vault without virtual shares (first-depositor inflation).
- [`ecrecover-zero-address`](https://github.com/tanod-labs/slither-detectors#ecrecover-zero-address): `ecrecover` result not checked against `address(0)`.
- [`signature-replay`](https://github.com/tanod-labs/slither-detectors#signature-replay): signature verification without a nonce or chain id.
- [`chainlink-stale-price`](https://github.com/tanod-labs/slither-detectors#chainlink-stale-price): Chainlink `latestRoundData` without staleness or answer validation.

## Limitations

pactlint is heuristic static analysis. It produces false positives and false negatives, only sees what Slither can compile, and does not reason about economics, governance, or off-chain components. It is not an audit and does not replace one.

Pinned versions: Slither 0.11.6. The detectors are installed from `tanod-labs/slither-detectors` at `detectors-ref`; pin it to a tag or commit for reproducible builds.

## Hosted triage

For a triaged report of a deployed contract or a single file, see [tanod.dev](https://tanod.dev) (paid per call via x402).

## License

MIT. See [LICENSE](LICENSE).
