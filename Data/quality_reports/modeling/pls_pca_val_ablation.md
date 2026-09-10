# Logistic PLS vs PCA vs current (val only)

Train-only rotation on **numeric** columns of `logistic_v1`. Dummy / missing-flag columns stay out of the rotation. Test sealed. CatBoost stays unrotated.

| run | pr_auc | roc_auc | log_loss | MW@10% |
|-----|--------|---------|----------|--------|
| logistic current (no rotation) | 0.0370 | 0.468 | 0.292 | 0.045 |
| PLS (8 components, train-fit) | 0.0393 | 0.485 | 0.317 | 0.096 |
| PCA 90% variance (**negative control**) | 0.0406 | 0.498 | 0.359 | 0.061 |
| Val chance PR-AUC | 0.041 | 0.500 | — | — |
| Unrotated CatBoost seed 42 (reference peak) | 0.144 | 0.794 | 0.187 | 0.335 |

**Do not ship PLS or PCA.** All three logistic runs are ~chance. PCA is not a useful “flex that implies the label”; it does not beat CatBoost. TabM PLS was not batch-run (low priority); use `electrum/05_tabm.ipynb` if needed.

Full table: [`retrain_val_compare.md`](retrain_val_compare.md).
