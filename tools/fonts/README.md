# 仓库自带中文字体（Laso CJK）

matplotlib 出图时要能在任何机器上正确显示中文——容器、Mac、Windows 上装的字体各不相同，而 matplotlib 对 macOS 的 .ttc 字体集合支持并不稳定（能找到字体名，渲染却出方块）。所以仓库自带一个字体文件，`tools/cjkfont.py` 优先使用它，其次才找系统字体。

- 来源：Noto Sans SC Regular（Noto Sans CJK 简体子集版），SIL Open Font License 1.1，见 `LICENSE.txt`。
- 内容：fontTools 子集：仓库文本里出现的全部汉字 + GB2312 一级常用字（3755 字）+ 拉丁、希腊字母、常用数学符号（Δ ≤ ≥ ≈ → −）与全角标点。
- 家族名改为 **Laso CJK**（OFL 要求改名后再分发）。
- 若图中出现方块，说明用了字集以外的生僻字：把该字加进 `demo*/build.py` 后运行 `python tools/cjkfont.py` 查看诊断，或扩大子集重做。
