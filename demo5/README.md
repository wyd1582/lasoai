# Demo 5 · 自驾育种 what-if（内部预测版，解析模型）

问题：如果湿实验（基因分型实验室、表型采集、繁殖执行）也自动化，育种闭环能快多少？`build.py` 把自动化能改变的四个量——依从性、表型覆盖、标签回流延迟、世代间隔——代入育种者方程与验证带宽，算出三个物种、四个情景的十年累计进展与假阳性数。展示站上的交互组件（`site/src/widgets.js` 的 `autolab`）实现同一个模型，`make verify` 用 node 对拍。

> 全部参数是假设口径（THEORY.md），不是任何客户的预测；准确度用 Daetwyler 上界 × 0.9，结果偏乐观，相对现状的百分比比绝对数可信。

```bash
cd demo5 && make report PYTHON=/path/to/python    # 约 2 秒；只需要 matplotlib
make verify PYTHON=/path/to/python                # 确定性 + JS/Python 对拍（需要 node）
```

| 文件 | 说明 |
|---|---|
| `build.py` | 模型、四个情景、图、报告（中英）、CLAIMS（中英）、`model.json`（预设 + 结果，供展示站读取）、RUN.json |
| `model.json` | 预设参数与结果；展示站的滑块从这里读默认值 |
| `figures/`、`figures/en/` | 三个物种的累计进展图；带宽与假阳性图 |
| `THEORY.md` / `THEORY.en.md` | 依据、极限、可证伪点 |
