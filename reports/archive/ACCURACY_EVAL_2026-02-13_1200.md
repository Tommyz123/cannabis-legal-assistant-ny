# ACCURACY_EVAL_REPORT

**Date:** 2026-02-13
**Rounds per question:** 3
**Total questions:** 20

## 1. Overview — All Questions

| ID | Category | avg_kw | avg_llm | consistency | Status |
|----|----------|--------|---------|-------------|--------|
| Q01 | A-许可证 | 100% | 5.0 | 1.00 | ✅ PASS |
| Q02 | A-许可证 | 100% | 1.0 | 1.00 | ❌ FAIL |
| Q03 | A-许可证 | 100% | 5.0 | 1.00 | ✅ PASS |
| Q04 | A-许可证 | 100% | 5.0 | 1.00 | ✅ PASS |
| Q05 | B-包装标签 | 100% | 5.0 | 1.00 | ✅ PASS |
| Q06 | B-包装标签 | 100% | 4.7 | 1.00 | ✅ PASS |
| Q07 | B-包装标签 | 0% | 5.0 | 1.00 | ❌ FAIL |
| Q08 | B-包装标签 | 60% | 4.0 | 1.00 | ✅ PASS |
| Q09 | C-广告营销 | 67% | 5.0 | 1.00 | ✅ PASS |
| Q10 | C-广告营销 | 100% | 5.0 | 1.00 | ✅ PASS |
| Q11 | C-广告营销 | 100% | 4.0 | 1.00 | ✅ PASS |
| Q12 | C-广告营销 | 100% | 3.0 | 1.00 | ✅ PASS |
| Q13 | D-违规罚则 | 100% | 4.3 | 1.00 | ✅ PASS |
| Q14 | D-违规罚则 | 50% | 4.0 | 1.00 | ❌ FAIL |
| Q15 | D-违规罚则 | 100% | 3.0 | 1.00 | ✅ PASS |
| Q16 | E-运营安全 | 100% | 5.0 | 1.00 | ✅ PASS |
| Q17 | E-运营安全 | 75% | 5.0 | 1.00 | ✅ PASS |
| Q18 | E-运营安全 | 100% | 4.0 | 1.00 | ✅ PASS |
| Q19 | F-策略审查 | 50% | 3.0 | 1.00 | ❌ FAIL |
| Q20 | F-策略审查 | 40% | 2.0 | 1.00 | ❌ FAIL |

## 2. Summary

| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Questions passed (kw≥60% AND llm≥3) | 15/20 | ≥15/20 | ✅ |
| Overall avg keyword rate | 82.1% | — | — |
| Overall avg LLM score | 4.10 | ≥3.5 | ✅ |
| Consistency pass (≥0.7) | 20/20 | ≥16/20 | ✅ |

## 3. Category Breakdown

| Category | Count | avg_kw | avg_llm | avg_cons | Passed |
|----------|-------|--------|---------|----------|--------|
| A-许可证 | 4 | 100% | 4.0 | 1.00 | 3/4 |
| B-包装标签 | 4 | 65% | 4.7 | 1.00 | 3/4 |
| C-广告营销 | 4 | 92% | 4.2 | 1.00 | 4/4 |
| D-违规罚则 | 3 | 83% | 3.8 | 1.00 | 2/3 |
| E-运营安全 | 3 | 92% | 4.7 | 1.00 | 3/3 |
| F-策略审查 | 2 | 45% | 2.5 | 1.00 | 0/2 |

## 4. Bottom 3 Questions (Worst Performers)

### Q20 — F-策略审查
- **Question:** Please review: 'Our cannabis products cure anxiety and treat depression naturally!'
- **avg_kw:** 40%  **avg_llm:** 2.0  **consistency:** 1.00
- **Required keywords:** ['cure', 'treat', 'medical', 'claim', 'prohibited']
- **Round 1 hits:** ['cure', 'treat']  llm=2
  > Answer preview: 审查结论：不合规 检测到医疗承诺表达: cure, treat
- **Round 2 hits:** ['cure', 'treat']  llm=2
  > Answer preview: 审查结论：不合规 检测到医疗承诺表达: cure, treat
- **Round 3 hits:** ['cure', 'treat']  llm=2
  > Answer preview: 审查结论：不合规 检测到医疗承诺表达: cure, treat

### Q07 — B-包装标签
- **Question:** Are cannabis dispensaries allowed to repackage products received from manufacturers?
- **avg_kw:** 0%  **avg_llm:** 5.0  **consistency:** 1.00
- **Required keywords:** ['prohibited', 'repackage']
- **Round 1 hits:** []  llm=5
  > Answer preview: No, cannabis dispensaries are not allowed to re-package products received from manufacturers. All products must be sold in their original manufacturer packaging that has been pre-approved and labeled 
- **Round 2 hits:** []  llm=5
  > Answer preview: No, cannabis dispensaries are not allowed to re-package products received from manufacturers. All products must be sold in original manufacturer packaging that has been pre-approved and labeled in com
- **Round 3 hits:** []  llm=5
  > Answer preview: No, cannabis dispensaries are not allowed to re-package products received from manufacturers. All products must be sold in their original manufacturer packaging that has been pre-approved and labeled 

### Q19 — F-策略审查
- **Question:** Please review: 'Get high with our stoner products! Great for everyone including kids!'
- **avg_kw:** 50%  **avg_llm:** 3.0  **consistency:** 1.00
- **Required keywords:** ['stoner', 'kid', 'prohibited', 'violation']
- **Round 1 hits:** ['stoner', 'kid']  llm=3
  > Answer preview: 审查结论：不合规 检测到禁用俚语: high, stoner 检测到儿童导向元素: kid
- **Round 2 hits:** ['stoner', 'kid']  llm=3
  > Answer preview: 审查结论：不合规 检测到禁用俚语: high, stoner 检测到儿童导向元素: kid
- **Round 3 hits:** ['stoner', 'kid']  llm=3
  > Answer preview: 审查结论：不合规 检测到禁用俚语: high, stoner 检测到儿童导向元素: kid

## 5. Consistency Issues (consistency < 0.7)

No consistency issues detected. All questions scored ≥ 0.7.
## 6. Findings & Recommendations

**5 question(s) failed** (avg_kw < 60% OR avg_llm < 3):

- **Q02** (A-许可证): kw=100% llm=1.0
- **Q07** (B-包装标签): kw=0% llm=5.0
  - Frequently missing keywords: ['prohibited', 'repackage']
- **Q14** (D-违规罚则): kw=50% llm=4.0
  - Frequently missing keywords: ['unlicensed', 'penalty']
- **Q19** (F-策略审查): kw=50% llm=3.0
  - Frequently missing keywords: ['prohibited', 'violation']
- **Q20** (F-策略审查): kw=40% llm=2.0
  - Frequently missing keywords: ['medical', 'claim', 'prohibited']

---

**✅ OVERALL PASS**  |  Questions passed: 15/20  |  avg_llm: 4.10  |  consistency_pass: 20/20
