# 许可证中文阅读说明

本文件帮助中文读者识别项目许可及相关材料，不替代许可证原文，也不改变其条款。

## HomeSpread 的许可

HomeSpread 的源码声明采用 **GPL-3.0-or-later**，即 GNU 通用公共许可证第 3 版或由使用者选择的后续版本。完整法律文本保存在 [LICENSE](LICENSE)，原有版权和许可声明保留在源码及 Git 历史中。

该许可允许在其条件下运行、研究、修改和再分发程序。再分发源码、修改版本或二进制时涉及保留通知、提供相应源码及许可等要求；具体适用条件请阅读原文，不把这一概述当作完整条款。原文也包含无担保和责任限制说明。

本 fork 将原作者的历史与中文化、macOS 适配、安全修复的提交区分开来。上游地址为 [humanlyj/HomeSpread](https://github.com/humanlyj/HomeSpread)，修改版地址为 [zherendong/HomeSpread](https://github.com/zherendong/HomeSpread)。macOS 应用包同时提供 `HomeSpread-source.zip`，用于交付对应修改源码。

## 第三方组件

第三方组件保留各自许可，不能把 HomeSpread 的许可名称套用到每个依赖上。

- [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 和 [third_party_licenses/](third_party_licenses/) 是仓库保留的上游 Windows 依赖与原文快照。
- macOS 构建根据 `requirements-macos.lock` 生成对应版本的 `THIRD-PARTY-NOTICES.md`、`dependency-inventory.json` 和 `third_party_licenses/`，放入 `.app` 的资源目录。
- 表中的包名、版本、SPDX 标识和原文标题保留原样，便于准确定位许可；它们不是遗漏的界面翻译。
- 缺少许可文件的条目不代表没有许可要求，应进一步查看相应组件的公开来源和发行材料。

常见名称的中文对应如下，具体要求仍以各自文本为准：

| 原文名称或标识 | 中文阅读名称 |
|---|---|
| GNU General Public License / GPL | GNU 通用公共许可证 |
| GNU Lesser General Public License / LGPL | GNU 宽通用公共许可证 |
| MIT | MIT 许可证 |
| BSD-2-Clause / BSD-3-Clause | BSD 两条款 / 三条款许可证 |
| Apache-2.0 | Apache 许可证 2.0 |
| MPL-2.0 | Mozilla 公共许可证 2.0 |
| PSF-2.0 | Python 软件基金会许可证 2.0 |
| ISC | ISC 许可证 |
| Public Domain | 元数据中的“公有领域”表述，不能代替对实际材料的核查 |

## 为什么保留法律原文

本次文档汉化覆盖项目说明、设计、操作流程、范例和开发资料。`LICENSE` 与 `third_party_licenses/` 内的第三方法律文本逐字保留，以免翻译改变原通知、版权归属或许可条件。阅读这些文件时，可先用本页和第三方清单定位所需文本。
