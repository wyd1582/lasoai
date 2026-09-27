# Demo 1 · 裁判拒绝了什么、为什么

来源：`demo1/out/rejected.csv`（台账 `candidate_transitions` 的最后一次拒绝理由）。共 134 个候选被拒，其中 66 个经过全量评估。

## 经过全量评估仍被拒的候选（按 ΔOOS 从高到低）

| campaign | DSL | 机制簇 | ΔOOS [90% 下界] | 拒绝理由 |
|---|---|---|---|---|
| broiler_B_s0_r20260927T1506 | champion() + region_weight(chrom=3, weight=2.84) | random_ops | +0.0110 [-0.0004] | failed gates: accuracy, incremental, research |
| broiler_B_s0_r20260927T1506 | champion() + qtl_prior(source='sim_noisy_qtl_prior', weight=3.38) + region_weight(chrom=5, weight=1.9) | random_ops | +0.0042 [-0.0097] | failed gates: incremental, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + lambda_scale(factor=1.53) | random_ops | +0.0015 [-0.0015] | failed gates: accuracy, incremental, plan, research |
| broiler_B_s0_r20260927T1506 | champion() + blend_pedigree(w=0.12) + lambda_scale(factor=1.23) | random_ops | +0.0011 [-0.0013] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + qtl_prior(source='sim_noisy_qtl_prior', weight=0.06) + region_weight(chrom=1, weight=0.82) | random_ops | +0.0008 [-0.0009] | failed gates: incremental, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + blend_pedigree(w=0.18) | random_ops | +0.0003 [-0.0024] | failed gates: incremental, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + blend_pedigree(w=0.06) + covariate(field='line') | random_ops | +0.0000 [-0.0001] | failed gates: incremental, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + covariate(field='farm') + qtl_prior(source='random_prior', weight=0.52) | random_ops | -0.0025 [-0.0057] | failed gates: incremental, plan, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + dominance(w=0.17) + lambda_scale(factor=0.72) | random_ops | -0.0041 [-0.0140] | failed gates: incremental, plan, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + grm_weights(scheme='maf_inverse') | random_ops | -0.0055 [-0.0162] | failed gates: incremental, plan, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + qtl_prior(source='random_prior', weight=0.18) + snp_subset(fraction=0.82, seed=903769, strategy='random') | random_ops | -0.0195 [-0.0304] | failed gates: incremental, plan, robustness, research |
| broiler_B_s0_r20260927T1506 | champion() + dominance(w=0.27) + region_weight(chrom=2, weight=4.41) | random_ops | -0.0410 [-0.0612] | failed gates: incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + lambda_scale(factor=2.0) | shrinkage | +0.0017 [-0.0034] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + blend_pedigree(w=0.3) | pedigree_blend | -0.0001 [-0.0053] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + grm_weights(power=-0.5, scheme='maf_power') | maf_weighting | -0.0002 [-0.0045] | failed gates: incremental, plan, research |
| broiler_D_s0_r20260927T1506 | champion() + dominance(w=0.2) | dominance | -0.0025 [-0.0121] | failed gates: incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + snp_subset(fraction=0.5, strategy='top_maf') | panel_reduction | -0.0027 [-0.0100] | failed gates: incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + covariate(field='sex') | fixed_effects | -0.0030 [-0.0057] | failed gates: incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + qtl_prior(source='random_prior', weight=2.0) | prior_weighting | -0.0107 [-0.0201] | failed gates: incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + region_weight(chrom=1, weight=3.0) | region_weighting | -0.0121 [-0.0215] | failed gates: incremental, plan, robustness, research |
| broiler_D_s0_r20260927T1506 | champion() + snp_subset(fraction=0.3, source='random_prior', strategy='prior_list') | prior_subset | -0.0786 [-0.1074] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_E_s0_r20260927T1506 | champion() + snp_subset(fraction=0.5, strategy='top_maf') | panel_reduction | +0.0032 [-0.0037] | failed gates: accuracy, incremental, robustness, research |
| broiler_E_s0_r20260927T1506 | champion() + covariate(field='sex') | fixed_effects | +0.0002 [-0.0009] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_E_s0_r20260927T1506 | champion() + grm_weights(scheme='maf_inverse') | maf_weighting | -0.0066 [-0.0153] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_E_s0_r20260927T1506 | champion() + qtl_prior(source='random_prior', weight=2.0) | prior_weighting | -0.0091 [-0.0187] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_F_s0_r20260927T1506 | champion() + snp_subset(strategy='random', fraction=0.3, seed=480422) | negative_control_random_snp | -0.0313 [-0.0571] | failed gates: incremental, plan, robustness, research |
| broiler_F_s0_r20260927T1506 | champion() + snp_subset(strategy='random', fraction=0.3, seed=749305) | negative_control_random_snp | -0.0323 [-0.0573] | failed gates: incremental, plan, robustness, research |
| broiler_F_s0_r20260927T1506 | champion() + snp_subset(strategy='random', fraction=0.3, seed=300601) | negative_control_random_snp | -0.0419 [-0.0654] | failed gates: incremental, plan, robustness, research |
| broiler_F_s0_r20260927T1506 | champion() + snp_subset(strategy='random', fraction=0.3, seed=256962) | negative_control_random_snp | -0.0482 [-0.0723] | failed gates: incremental, plan, robustness, research |
| broiler_F_s0_r20260927T1506 | champion() + snp_subset(strategy='random', fraction=0.3, seed=933561) | negative_control_random_snp | -0.0634 [-0.0890] | failed gates: accuracy, incremental, plan, robustness, research |
| broiler_G_s0_r20260927T1506 | champion() + qtl_prior(source='sim_noisy_qtl_prior', weight=1.0) | challenger_prior_sim_noisy_qtl_prior | +0.0012 [-0.0037] | failed gates: incremental, robustness, research |
| broiler_G_s0_r20260927T1506 | champion() + qtl_prior(source='sim_noisy_qtl_prior', weight=2.0) | challenger_prior_sim_noisy_qtl_prior | -0.0002 [-0.0085] | failed gates: incremental, plan, research |
| broiler_G_s0_r20260927T1506 | champion() + qtl_prior(source='sim_noisy_qtl_prior', weight=4.0) | challenger_prior_sim_noisy_qtl_prior | -0.0047 [-0.0175] | failed gates: incremental, plan, robustness, research |
| broiler_G_s0_r20260927T1506 | champion() + qtl_prior(source='random_prior', weight=1.0) | negative_control_prior | -0.0052 [-0.0108] | failed gates: incremental, plan, robustness, research |
| broiler_G_s0_r20260927T1506 | champion() + qtl_prior(source='random_prior', weight=4.0) | negative_control_prior | -0.0202 [-0.0344] | failed gates: incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + dominance(w=0.07) + snp_subset(fraction=0.44, seed=153825, strategy='top_maf') | random_ops | +0.0100 [-0.0019] | failed gates: accuracy, incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + snp_subset(fraction=0.3, seed=641738, strategy='top_maf') | random_ops | +0.0078 [-0.0083] | failed gates: incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + region_weight(chrom=1, weight=0.82) + snp_subset(fraction=0.21, seed=127127, strategy='top_maf') | random_ops | +0.0067 [-0.0146] | failed gates: incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + covariate(field='line') + grm_weights(power=0.58, scheme='maf_power') | random_ops | +0.0010 [-0.0013] | failed gates: accuracy, incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + grm_weights(power=0.53, scheme='maf_power') | random_ops | +0.0009 [-0.0013] | failed gates: accuracy, incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + grm_weights(power=-0.24, scheme='maf_power') + lambda_scale(factor=2.12) | random_ops | +0.0009 [-0.0020] | failed gates: accuracy, incremental, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + grm_weights(power=0.13, scheme='maf_power') + region_weight(chrom=4, weight=0.68) | random_ops | +0.0002 [-0.0005] | failed gates: accuracy, incremental, plan, robustness, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + region_weight(chrom=1, weight=1.14) | random_ops | -0.0000 [-0.0001] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + covariate(field='line') + region_weight(chrom=2, weight=0.09) | random_ops | -0.0001 [-0.0009] | failed gates: accuracy, incremental, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + grm_weights(power=-0.78, scheme='maf_power') | random_ops | -0.0004 [-0.0064] | failed gates: accuracy, incremental, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + covariate(field='line') + lambda_scale(factor=0.4) | random_ops | -0.0012 [-0.0056] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_B_s0_r20260927T1529 | champion() + grm_weights(power=0.65, scheme='maf_power') + snp_subset(fraction=0.77, seed=452625, strategy='random') | random_ops | -0.0034 [-0.0072] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_C_s0_r20260927T1529 | champion() + region_weight(chrom=1, weight=3.0) | region_weighting | -0.0000 [-0.0016] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + snp_subset(fraction=0.25, strategy='top_maf') | panel_reduction | +0.0095 [-0.0098] | failed gates: incremental, plan, robustness, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + snp_subset(fraction=0.5, strategy='top_maf') | panel_reduction | +0.0059 [-0.0031] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + dominance(w=0.2) | dominance | +0.0012 [-0.0033] | failed gates: accuracy, incremental, robustness, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + lambda_scale(factor=2.0) | shrinkage | +0.0010 [-0.0015] | failed gates: accuracy, incremental, robustness, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + dominance(w=0.1) | dominance | +0.0006 [-0.0017] | failed gates: accuracy, incremental, robustness, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + grm_weights(scheme='maf_inverse') | maf_weighting | +0.0002 [-0.0082] | failed gates: accuracy, incremental, robustness, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + region_weight(chrom=2, weight=1.5) | region_weighting | +0.0001 [-0.0003] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + covariate(field='sex') | fixed_effects | +0.0000 [+0.0000] | failed gates: accuracy, incremental, research |
| pig_cleveland_D_s0_r20260927T1529 | champion() + grm_weights(power=-0.5, scheme='maf_power') | maf_weighting | -0.0006 [-0.0038] | failed gates: accuracy, incremental, research |
| pig_cleveland_E_s0_r20260927T1529 | champion() + region_weight(chrom=1, weight=3.0) | region_weighting | +0.0019 [+0.0002] | failed gates: accuracy, research |
| pig_cleveland_E_s0_r20260927T1529 | champion() + lambda_scale(factor=2.0) | shrinkage | +0.0004 [-0.0023] | failed gates: accuracy, incremental, research |
| pig_cleveland_E_s0_r20260927T1529 | champion() + covariate(field='sex') | fixed_effects | +0.0000 [+0.0000] | failed gates: accuracy, incremental, research |
| pig_cleveland_E_s0_r20260927T1529 | champion() + grm_weights(power=-0.5, scheme='maf_power') | maf_weighting | -0.0016 [-0.0043] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_F_s0_r20260927T1529 | champion() + snp_subset(strategy='random', fraction=0.3, seed=480422) | negative_control_random_snp | +0.0141 [+0.0064] | failed gates: accuracy, plan |
| pig_cleveland_F_s0_r20260927T1529 | champion() + snp_subset(strategy='random', fraction=0.3, seed=256962) | negative_control_random_snp | +0.0015 [-0.0074] | failed gates: accuracy, incremental, plan, robustness, research |
| pig_cleveland_F_s0_r20260927T1529 | champion() + snp_subset(strategy='random', fraction=0.3, seed=933561) | negative_control_random_snp | -0.0044 [-0.0135] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_F_s0_r20260927T1529 | champion() + snp_subset(strategy='random', fraction=0.3, seed=300601) | negative_control_random_snp | -0.0083 [-0.0176] | failed gates: accuracy, incremental, plan, research |
| pig_cleveland_F_s0_r20260927T1529 | champion() + snp_subset(strategy='random', fraction=0.3, seed=749305) | negative_control_random_snp | -0.0084 [-0.0165] | failed gates: accuracy, incremental, research |

## 未进入全量评估就被拒的候选（评审者、有效性门、重试上限）

| campaign | 理由 | n |
|---|---|---|
| broiler_D_s0_r20260927T1506 | NEED_OPERATOR: minimal spec: env_covariate is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| broiler_D_s0_r20260927T1506 | NEED_OPERATOR: minimal spec: multi_trait is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| broiler_D_s0_r20260927T1506 | hypothesis: The mechanism as stated requires phenotypes recorded after selection_date. | 14 |
| broiler_D_s0_r20260927T1506 | retry limit exceeded after Critic RETURN | 3 |
| broiler_D_s0_r20260927T1506 | semantic_hash_unique: f0df7ef8ec1c4e19 | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_425c0505e8 after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_4cc5a21dff after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_7097d668f0 after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_718729e249 after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_80b718f4e9 after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_a27e4e9ec3 after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_a58fa5fa70 after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_af16fb08fd after build | 1 |
| broiler_D_s0_r20260927T1506 | superseded by k_c578819035 after build | 1 |
| broiler_E_s0_r20260927T1506 | NEED_OPERATOR: minimal spec: env_covariate is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| broiler_E_s0_r20260927T1506 | NEED_OPERATOR: minimal spec: multi_trait is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| broiler_E_s0_r20260927T1506 | hypothesis: The mechanism as stated requires phenotypes recorded after selection_date. | 1 |
| broiler_E_s0_r20260927T1506 | superseded by k_005812d976 after build | 1 |
| broiler_E_s0_r20260927T1506 | superseded by k_0b812333d7 after build | 1 |
| broiler_E_s0_r20260927T1506 | superseded by k_4ea7404876 after build | 1 |
| broiler_E_s0_r20260927T1506 | superseded by k_76322dea01 after build | 1 |
| broiler_E_s0_r20260927T1506 | superseded by k_e97ed130e5 after build | 1 |
| broiler_G_s0_r20260927T1506 | semantic_hash_unique: 3dea75008cd3137c | 1 |
| pig_cleveland_D_s0_r20260927T1529 | NEED_OPERATOR: grammar violation: qtl_prior: unknown prior source 'none'; known: [] | 2 |
| pig_cleveland_D_s0_r20260927T1529 | NEED_OPERATOR: grammar violation: snp_subset: unknown prior source 'none' | 1 |
| pig_cleveland_D_s0_r20260927T1529 | NEED_OPERATOR: minimal spec: env_covariate is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| pig_cleveland_D_s0_r20260927T1529 | NEED_OPERATOR: minimal spec: multi_trait is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| pig_cleveland_D_s0_r20260927T1529 | hypothesis: The mechanism as stated requires phenotypes recorded after selection_date. | 14 |
| pig_cleveland_D_s0_r20260927T1529 | retry limit exceeded after Critic RETURN | 2 |
| pig_cleveland_D_s0_r20260927T1529 | semantic_hash_unique: 2cf57e98b5650493 | 1 |
| pig_cleveland_D_s0_r20260927T1529 | superseded by k_0a54ac3f0c after build | 1 |
| pig_cleveland_D_s0_r20260927T1529 | superseded by k_48e00e0371 after build | 1 |
| pig_cleveland_E_s0_r20260927T1529 | NEED_OPERATOR: minimal spec: env_covariate is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| pig_cleveland_E_s0_r20260927T1529 | NEED_OPERATOR: minimal spec: multi_trait is reserved; minimal spec required before use; needs a second phenotype/environment table joined on animal_id with its own available_at | 1 |
| pig_cleveland_E_s0_r20260927T1529 | hypothesis: The mechanism as stated requires phenotypes recorded after selection_date. | 2 |
| pig_cleveland_E_s0_r20260927T1529 | superseded by k_087b744f8d after build | 1 |
| pig_cleveland_E_s0_r20260927T1529 | superseded by k_8a00069074 after build | 1 |

## 评审者（Critic）在写代码前的拒绝与退回

| campaign_id | verdict | leak_type | n |
|---|---|---|---|
| broiler_D_s0_r20260927T1506 | REJECT | ["temporal"] | 14 |
| broiler_D_s0_r20260927T1506 | RETURN | ["dispersion"] | 3 |
| broiler_D_s0_r20260927T1506 | RETURN | ["plan"] | 6 |
| broiler_E_s0_r20260927T1506 | REJECT | ["temporal"] | 1 |
| pig_cleveland_D_s0_r20260927T1529 | REJECT | ["temporal"] | 14 |
| pig_cleveland_D_s0_r20260927T1529 | RETURN | ["dispersion"] | 3 |
| pig_cleveland_D_s0_r20260927T1529 | RETURN | ["plan"] | 3 |
| pig_cleveland_E_s0_r20260927T1529 | REJECT | ["temporal"] | 2 |
