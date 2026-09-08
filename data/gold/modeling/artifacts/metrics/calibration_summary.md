# Calibration summary (validation only)

**Primary metrics:** 5-fold cross-fitted calibration on val.
**Secondary:** full-val fit (deployment artifact; not for selection).
**Test / score sealed.**

## `catboost_tuned`

### platt
- CV Brier=0.038465533216433506 ECE=0.006591946288867569 LogLoss=0.1529473470139325 (raw Brier=0.04070262885745357)
- Full-val ops (deployment fit): P@10%=0.1317365269461078 R@10%=0.3188405797101449 MW@10%=0.2914204198084369
### isotonic
- CV Brier=0.03853344591905466 ECE=0.004622351736730996 LogLoss=0.15674787417157915 (raw Brier=0.04070262885745357)
- Full-val ops (deployment fit): P@10%=0.1437125748502994 R@10%=0.34782608695652173 MW@10%=0.3281027104136947
- Best by CV Brier: `platt`

## `catboost_champion_seed_2026`

### platt
- CV Brier=0.038773171406418554 ECE=0.008283445238709988 LogLoss=0.1557742978987571 (raw Brier=0.041212869871010624)
- Full-val ops (deployment fit): P@10%=0.10179640718562874 R@10%=0.2463768115942029 MW@10%=0.22671693499082943
### isotonic
- CV Brier=0.03852932309082217 ECE=0.006537598077261811 LogLoss=0.15909126646097183 (raw Brier=0.041212869871010624)
- Full-val ops (deployment fit): P@10%=0.10179640718562874 R@10%=0.2463768115942029 MW@10%=0.19095170165070308
- Best by CV Brier: `isotonic`
