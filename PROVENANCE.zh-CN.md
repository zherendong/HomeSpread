# HomeSpread 来源核查

核查日期：2026-11-13。对象为 [humanlyj/HomeSpread](https://github.com/humanlyj/HomeSpread) 的提交 `0cfbc6866e9748105cbc3c9e743ad0b1788e6775`，不把本 fork 新增的中文、macOS 和安全修改归为上游代码。

## 结论

公开记录支持该项目为作者基于开源组件开发的独立应用。本次未发现足以认定其抄袭同类项目的证据。这个结论不是“全部代码从零原创”的保证：项目明确依赖 pymobiledevice3、Qt/PySide6 等已有软件，算法和框架惯用代码也可能相似。未公开、未被索引的来源，以及经过大幅改写的代码，不在这次核查可以排除的范围内。

## 仓库历史与署名

- [GitHub 仓库元数据](https://api.github.com/repos/humanlyj/HomeSpread) 显示创建时间为 2026-08-21，`fork=false`。这只说明 GitHub 没有记录其为 fork，不单独证明原创。
- 获取完整历史后，共有 13 次上游提交。最早提交为 [0db0696](https://github.com/humanlyj/HomeSpread/commit/0db069647993c3529e035ed3e1afd028321be897)，日期 2026-08-21，已包含主体实现。后续提交记录了打包、日志保留、默认应用识别、HomeBoard 更名为 HomeSpread 和商店发布。首次提交包含较多已有实现，不能据此重建开发前的全部来源。
- [CLAUDE.md](https://github.com/humanlyj/HomeSpread/blob/0cfbc6866e9748105cbc3c9e743ad0b1788e6775/CLAUDE.md) 有对应的设计和开发记录。提交包含 Claude 协作署名；AI 辅助开发本身不能作为抄袭或原创的证明。
- [README](https://github.com/humanlyj/HomeSpread/blob/0cfbc6866e9748105cbc3c9e743ad0b1788e6775/README.md)、[第三方清单](https://github.com/humanlyj/HomeSpread/blob/0cfbc6866e9748105cbc3c9e743ad0b1788e6775/THIRD-PARTY-NOTICES.md) 及许可目录明确说明依赖来源，项目声明采用 GPL-3.0-or-later。本 fork 保留这些署名和许可证。
- 核查时 GitHub Issues 列表为空。公开搜索没有查到针对该仓库的抄袭指控；搜索覆盖不完整，不能将无结果当作不存在争议的证明。

## 同类项目比对

比对上游 `src/`、`scripts/` 的 Python 文件与下列公开仓库，不执行下载的程序。词法检查去掉注释、换行和缩进 token，搜索连续 50 个相同 token 的窗口，再人工查看命中。该检查可发现直接或局部逐字复用，无法可靠识别重命名、跨语言移植或结构重写。

| 对照项目 | 核查提交 | Python 文件数 | 检查结果 |
|---|---|---:|---|
| [kurtkluth/IconTiller](https://github.com/kurtkluth/IconTiller) | `5b301b8c67c7d559e77d6628a3716f97cc747e5d` | 21 | 没有命中连续 50 token 窗口；使用 Tkinter，和 HomeSpread 的 Qt 界面实现不同。 |
| [YakupEmreYerli/ios-homescreen](https://github.com/YakupEmreYerli/ios-homescreen) | `97649547dbc44295e451c6bf130a87404481e10c` | 43 | 一段 114 token 的最长公共子序列动态规划递推相同；其余 Python 代码未命中阈值。 |
| [huangzheng2016/ios-icon-mcp](https://github.com/huangzheng2016/ios-icon-mcp) | `fadd1c26bd84c36850f07bb6cc68fbc2772e34cc` | 1 | 没有命中阈值；提供 MCP 接口。 |
| [tmad4000/iphone-layout-tool](https://github.com/tmad4000/iphone-layout-tool) | `4d9ca9eb19bc451b61ba61d812c4e9995dab1752` | 1 | 没有命中阈值；使用 cfgutil/AirTraffic 转换流程。 |

命中的算法位于 HomeSpread `src/ipsm/layout.py` 与 ios-homescreen `src/ios_homescreen/model.py`。它在 HomeSpread 最早的 2026-08-21 提交中已存在；对照仓库的 GitHub 创建日期为 2026-10-10。这个时间顺序与常见算法性质，不支持据此认定 HomeSpread 从该公开仓库复制。也不能反向据此指控对照项目抄袭。

另检查了 HomeSpread 的 `FlowLayout` 与 [Qt 官方 Flow Layout 示例](https://doc.qt.io/qtforpython-6/examples/example_widgets_layouts_flowlayout.html)。两者采用常见的逐项累计宽度、超宽换行方式，Qt 必需接口相同，但成员名、边距和间距处理有所不同。这是框架模式相似，单靠它无法确定直接来源或作者关系。

GitHub 代码搜索还查询了 `_plan_spill`、`shows_on_home_screen` 与 `LayoutDocument`/`suggest_group_name` 组合及特征韩文短句，未得到能建立复制关系的结果。代码搜索没有完整覆盖目标仓库，因此只作为辅助检查。

## 本 fork 的标识与隐私

本 fork 保留上游提交历史，中文化、macOS 适配和安全修复作为独立提交记录，沿用项目许可。没有把设备备份、配对凭据、日志、图标缓存、虚拟环境或本机应用包提交到 GitHub。发布的验证说明只保留技术环境和结论，不公开个人设备清单或原始布局。
