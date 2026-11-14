# HomeSpread（早期仓库目录名：iPhoneScreenManager）

## 只读证据、预检与模拟的边界

`mac.zh.4` 增加 `.hsevidence` 查询收据和 `.hspreflight` 阻塞报告。界面仅加载本地文件，不调用采集器；真实 USB 采集必须作为另行明确范围的操作，不能因“预检”而自动执行。当前阶段未运行真机采集或写入。假设备模拟器没有真实传输入口，匹配只代表导出字段检查，所有结果仍 `can_write=False`。

证据、草稿和报告都含私人布局信息，不能进入 Git 或源码包。新只读适配器固定本地端点，不接受环境变量重定向，不自动配对。具体数据结构及限制见 `_workspace/02_contracts/evidence-preflight.contract.md`。

## 离线草稿与设备写入的区别

`mac.zh.3` 在独立 `OfflineDraft` 中开放同页两个普通 App 的交换、差异查看、撤销/重做和 `.hsdraft` 保存/重开。它不修改原始 `LayoutDocument` 的只读规则，也不进入 `DeviceWorker` 的设备路径。Duo、小组件和未知布局的所有设备写入仍由现有策略拒绝。草稿文件是含个人数据的本机产物，不是可恢复的手机备份，不能提交或打包。

纯编辑规则位于 `ipsm.draft_rules`，研究入口仅做兼容导出。文件验证、重放与界面边界见 `_workspace/02_contracts/offline-draft.contract.md` 和 `_workspace/06_offline-draft-qa.md`。

## 当前能力限制：小组件与 Duo

`mac.zh.2` 增加只读的小组件跨格及 Duo 双页预览。所有写入入口必须遵守 `write_policy.py`：拒绝 Duo 型号、含小组件/堆叠、未知项或空位的当前/目标布局，包括原样校验与恢复。会话成功标记不能覆盖此限制。旧文中的校验失败后允许恢复，仅适用于设备、当前状态和备份都通过能力检查的普通布局。

开发与验收使用合成数据或明确授权的本地备份，不能把个人布局、截图和图标提交到仓库；本次不连接或写入手机。相关证据见 `_workspace/05_widget-duo-qa.md`。

## 开发协作：iPhone 主屏幕管理桌面应用

**目标：** 在电脑的同一画面展开 iPhone 的多页主屏幕，通过拖放编辑，再将明确确认的结果应用到设备。当前交付目标是中文 macOS 移植版，保留上游 Windows 实现与历史资料。

**触发条件：** 处理本项目的规划、设计、实现和验证任务时使用 `iphone-homescreen-orchestrator` 技能。继续工作、重新执行、局部修改和反馈修订同样适用。简单问题或单个文件查询可以直接处理。

**核心约束：** 非越狱 iPhone 存在布局写入路径：`com.apple.springboardservices` 的 `setIconState`。当前路径使用 USB、解锁和“信任”，不依赖越狱、开发者模式、Xcode 或 WebDriverAgent。它会**替换整份布局**；遗漏未知元素（小组件等）可能造成损失。安全要求包括原文保留、设备归属、写前状态检查、备份完整性和写后核对。**备份不保证完全回滚**：App 资源库回填无法通过恢复撤销，断线、系统版本差异和未知布局的行为也不能凭推测保证。发生设计分歧时，先检查是否会危及用户的主屏幕。

## 中文 macOS 版的现行规则（2026-11-13）

- 使用 Python、PySide6 和 `pymobiledevice3`；Apple Silicon `.app` 的最低系统版本为 macOS 14。macOS 连接服务为 `/var/run/usbmuxd`，Windows 历史路径为 `127.0.0.1:27015`。只使用 USB，多设备时不擅自选第一台，不自动回退 Wi-Fi。
- 普通读取、获取图标和电脑内编辑不写手机。编辑应用前要求本次会话已有成功的真实写入及读回校验；正常流程是用户明确确认“原样写回校验”。读取新布局或操作失败后验证标记失效。
- **恢复是独立确认的恢复通道。** 即使原样校验失败，仍可从当前设备的完整备份恢复。恢复前保存当前状态，恢复后重读核对；恢复结果安全时也会更新本会话的 `write_verified`，因此不能写成“只有原样校验能建立编辑许可”。不自动恢复或重复写入。
- 所有写入经过 `backup.guarded_write`。普通编辑传入 `document.origin` 作为 `expected_state`，手机最新布局与其不同就停止。条目删除、复制、原始内容改变或未知元素被间接移动也会被拒绝。
- 备份位于 `~/Library/Application Support/HomeSpread/backups/<设备指纹>/`，包含原始二进制 `.plist`、可读 `.json` 和校验用 `.meta.json`。归属、持久化或完整性检查失败就不写设备。旧版或外部文件可以预览，不能绕过设备归属检查用于恢复。
- 日志和设置也位于用户的 Application Support 目录；图标位于 `~/Library/Caches/HomeSpread/`；新建配对缓存位于资料目录的 `pairing/`，不进入报告和分发包。完整设备标识不写入公开文档，日志脱敏不等于整份布局匿名化。
- 默认简体中文，可切换 English 和韩语。窗口、确认框、诊断命令和用户文档须准确描述真实行为；内部日志与 API 名称不能为翻译而改变协议语义。
- macOS 包含修改版对应源码、依赖清单和许可。上游源码链接不能代替本地修改源码。重建时重新生成随包文档和源码归档，避免旧产物与新代码不一致。
- 本机已记录真机只读连接、布局读取和备份验证；没有执行真实布局写回或恢复。自动测试与上游 Windows 成功记录不能替代当前手机/iOS 的真实写入验证。具体结果见 `README.zh-CN.md`、`SECURITY_AUDIT.zh-CN.md` 和 `_workspace/04_macos-qa_final-report.md`。

## 上游设计与验证记录（2026-08-19 至 2026-09-01）

以下完整保留上游的设计依据与时间线。设备写入结果针对当时的 Windows 应用、iPhone 14 / iOS 26.1；商店、支付和许可流程描述的是当时调查和操作，不能作为当前服务政策或本次 Mac 写入验收的替代证据。

**原样写回已验证（2026-08-19，iPhone 14 / iOS 26.1）：** 309 个条目的顺序、文件夹内容和日期都被保留，丢失和移动均为 0。发现的副作用是 **iOS 将仅在 App 资源库中的应用追加到最后一页**。`setIconState` 没有表达“已安装但不在主屏幕”的字段，恢复备份也会再次写入，因此不能撤销这个副作用。必须提前告诉用户。

**文件夹结构核验（2026-08-20）：** 当时设备上的 26 个文件夹全部只有 `displayName`、`iconLists`、`listType` 三个键。这是当时实现创建文件夹的依据，而不是所有未来 iOS 版本的结构保证。重命名只改变 `displayName`，其余 raw 字段原样保留。

**编辑写入核验（2026-08-20，同一设备）：** 实际拖动图标后应用两次，丢失 0、iOS 新增 0。第二次发送的 plist 与设备读回的 plist 完全一致，证明当时环境的读取、编辑与写入流程能够贯通。

**iOS 会删除空文件夹（2026-08-20 真机结果）：** 发送了三个空文件夹（Cloud、生产力、实用工具）后，iOS 删除了它们，并使后续条目依次前移。比较器报告“丢失 3 项、意外移动 39 项”；实际应用没有丢失，但提示看起来像事故。因此模型在最后一个条目移出时就删除空文件夹，使发送结果与系统会保留的结构一致，让核验警告指向真正异常。

**主屏幕也支持连续挤移（2026-08-20）：** 将应用从下一页拖到已满页面的具体位置，后续条目顺移，溢出的最后一个应用进入下一页开头。后页也满时继续传递，必要时新增一页。主页与文件夹共享一套 `_plan_spill`，只由 `_page_family` 提供容量与最大页数差异。

**文件夹内的挤移和空页清理（2026-08-20）：** 把条目插到已满文件夹页的具体位置时，后续条目顺移，溢出项进入下一页开头。页面完全变空时删除该页。若保留空页，iOS 可能自行删除并推动后续项，使比较器误报丢失或移动；这与空文件夹的情况相同。

**Windows 准备状态以端口判断（2026-08-20）：** 当时使用 Apple 组件提供的 `127.0.0.1:27015`。能否连接该端口是实际就绪依据；按安装目录猜测软件是否安装，只用于区分“已安装但尚未运行”与“没有安装”的提示，不用于阻止操作。启动指南每 3 秒刷新。这是 Windows 规则；macOS 检查本地 Unix socket。

**产品名与兼容性副标题分开（2026-08-20，2026-08-26 改名）：** 上游依据当时查阅的 Apple 商标说明，将产品名 HomeSpread 与兼容性副标题 `Mobile layout manager for iOS` 分别放在 `product.py` 中，商店名称只使用 `NAME`。不在自己的产品名中嵌入 `iOS` 或 `iPhone`。代码直接写名称会产生多个修改点，因此测试禁止说明文字之外的名称重复声明。

**名称还受注册占用限制（2026-08-26）：** 初始名称 `HomeBoard` 在 Partner Center 已被使用。上游查询了 `PageDeck`（电商 SaaS）、`IconDesk`（人才管理 SaaS）、`Screenlay`、`Iconlay`、`Screenboard`（Mac 应用），当时只有 HomeSpread 未找到占用。改名除 `NAME` 外，还涉及 `.spec` 文件名与 `name=`、`build_exe.bat`、`keep_data.py` 的 `dist\` 路径、版权行、文档和资料目录（文档\HomeSpread\）。`SOURCE_URL` 必须在仓库实际迁移后修改，不能先指向尚不存在的地址。

**赞助不提供额外权益（2026-08-20）：** 上游按当时 Store 政策 10.8.2 的调查，把外部支付限定为无对价的自愿赞助。如果赞助后获得功能或去除广告，需要重新处理 Microsoft 应用内支付要求。现有按钮不提供功能奖励。

**采用 GPL-3.0-or-later（2026-08-20）：** 设备通信库 `pymobiledevice3` 采用该许可，HomeSpread 也以 GPL-3.0-or-later 发布。为了使只拿到程序的人也能阅读许可，Windows 包内包含 `LICENSE` 和第三方告知，由“关于”窗口显示。上游还通过 `product.SOURCE_URL` 提供源码入口；无地址时仅显示向分发者索取源码的提示。可分发版本应提供真实可达的对应源码，当前 Mac 修改版还在包内提供本次源码归档。

**隐私说明必须符合实际行为（2026-08-20）：** 当时上游根据 Store 政策 10.5.1 为 Win32 产品提供隐私说明。没有自动上传不等于没有本地数据，说明必须列出 `backups/`、`logs/`、`cache/icons/`、`settings.json`、`127.0.0.1:27015`、只保留前四字符的 UDID，以及用户点击后才打开的赞助和 Store 页面。测试将原文与 `settings_path()` 等实现核对，说明也随 exe 分发，可离线阅读。当前 Mac 的目录、连接服务与配对缓存见中文隐私说明。

**GPL 与 Store 的分发路径（2026-08-20 调查）：** 上游当时查阅的开发者协议允许提交自己的许可，并允许在 FOSS 所需范围内优先适用相关复制、修改和再分发权利，VLC 是其参考案例。后续需要验证的是 MSIX 打包后的行为：安装位置的写入可能被虚拟化，必须确认 `paths.data_root()` 指向用户能够找到、并实际保留备份的位置。

**MSIX 实际安装验证（2026-08-26）：** 上游创建未签名 `.msix` 并安装到 `C:\Program Files\WindowsApps\`，确认该目录不可写；应用改在“文档\HomeSpread\”生成 `backups\` 和 `logs\`，图标仍保存在 `%TEMP%`。`127.0.0.1:27015` 可用，因为该包使用 `Windows.FullTrustApplication`，不在 AppContainer 内。测试安装没有向信任库添加自签证书，而是在开发身份的 `Publisher` 后附 Windows 未签名命名空间标记，使用 `-AllowUnsigned`。标记只放在 `identity.dev.json`，没有写入商店身份。

**允许列表按路径保存，而路径随版本变化（2026-08-26）：** Windows“受控文件夹访问”的允许项绑定 exe 路径。MSIX 路径带版本号，如 `...HomeSpread_1.0.19.0_x64__cx182f...`，升级可能需要重新允许。应用不能靠自身代码改变该系统规则，因此错误提示须明确指出此原因。

**Windows 启动时间受打包方式影响（2026-08-21）：** 单文件 exe 每次需将内部约 72MB 解压到临时目录；21 秒实测启动中，16.5 秒用于解压，此时 Python 尚未启动，Qt 也无法显示窗口。改为文件夹分发后实测约 2.3 秒，代价是分发一整个目录，展开体积由 72MB 增至 169MB。剩余等待由约 0.3 秒出现的 bootloader 启动画面覆盖。该画面依赖 Tk，Windows spec 不能将 `tkinter` 排除；MSIX 也使用目录形式。这些数字和 Tk 启动画面只属于当时 Windows 包，Mac spec 不使用该启动图。

**源码公开与商店资料（2026-08-21）：** 上游仓库地址同时用于 `product.SOURCE_URL`、Partner Center 的 `PRIVACY.md` URL 和分发入口。`logs/`、`backups/`、`cache/` 是实际设备数据，不能上传；`.gitignore` 同时排除这些目录、`dist*/`、`build*/` 和 `settings.json`。

**编辑规则的真机验证（2026-08-21，iPhone 14 / iOS 26.1）：** 上游使用真实布局验证创建与重命名文件夹、文件夹增页、文件夹挤移、主屏幕挤移和清理空位。该布局有 2 个主页、35 个文件夹，284 个应用大多在文件夹内。15 项检查全部通过：4 个编辑阶段后仍保留 284 个应用，空位数为 0，撤销 21 次后与原文完全一致。为了验证新建文件夹能否被设备接受，上游还执行了最小编辑写入；发送和读回的 plist 完全一致，随后恢复的布局也一致。这是该设备上的历史结果，不是普遍回滚保证。

**没有新增不代表副作用消失（2026-08-21）：** 当天两次写入没有回填应用，因为当时只有 App 资源库中存在的应用数为 0，布局已在 8 月 19 日经历过一次回填。回填是存在未布局应用时可能发生的系统行为。

**系统应用也可能回填（2026-08-21）：** 对照 8 月 19 日两份备份发现，追加的 4 个应用中有 Apple 的“放大器”（`com.apple.Magnifier`）。只查询 `application_type="User"` 会漏报它。但也不能把系统应用全部算入：当时设备有 232 个系统应用，其中 190 个不应出现在主屏幕。筛选依据包括 `SBAppTags` 的 `hidden`（184 个无界面内部组件）、没有图标（1 个）、`SBIconVisibilitySetByAppPreference`（4 个自行决定可见性的应用）和不在 `LSSupportedRegions` 内（1 个，News 当时限定 US/GB/AU/CA）。剩下 40 个候选，未布局数为 0，与当天实际回填 0 个相符。地区从 locale（如 `ko_KR`）获得；`RegionInfo` 的 `KH/A` 是 Apple 部件地区码，不是 ISO 国家代码，ISO 的 `KH` 表示柬埔寨。无法读取地区时，只取消地区过滤，避免无依据漏报。

**跳过场景不算通过（2026-08-21）：** 首次运行的两项挤移场景因“没有合适对象”被跳过。验证脚本只在主页找独立应用，而该设备的大部分应用位于文件夹内。上游扩大到文件夹内部寻找对象后重新验证，并在最终报告中把跳过与通过分别计数。

**保存位置取决于数据用途（2026-08-21）：** 备份用于恢复，日志用于事后诊断，二者都需要保留。图标可以重新下载，当时 287 个图标耗时 7.4 秒，因此只有图标进入 Windows 临时目录。上游测试电脑启用了包括临时文件清理的 Storage Sense；把备份放入 TEMP 会让系统清理机制删除恢复点。

**Store 安装目录不能用于资料写入（2026-08-21）：** 上游测试中 `C:\Program Files\WindowsApps\` 由 `NT AUTHORITY\SYSTEM` 所有，以管理员权限也不能直接写入。因此打包安装时 `data_root()` 转向真实文档目录。上游没有选 `%LOCALAPPDATA%`，因为包内可能被重定向到 `Packages\...\LocalCache\`，用户不容易找到。文档目录用 `SHGetKnownFolderPath` 查询；当时测试机实际目录为 `D:\Personal\Documents`，拼接 `%USERPROFILE%\Documents` 会落到错误位置。包身份用 `GetCurrentPackageFamilyName` 查询，并同时要求 `is_frozen()`，否则 Microsoft Store 版开发 Python 即使运行源码也可能带包身份，造成开发资料位置意外变化。对商店安装用户不能再提示“移动程序目录”，应给出适用的权限说明。

**赞助渠道受收款地区限制（2026-08-28）：** 当时 PayPal 按钮返回 `Donations aren't supported in this organization's country`。调查得到两个条件：相关赞助产品要求企业账号，而韩国注册账号还受到收款地区限制，升级企业账号不能消除后者。上游也调查了 Buy Me a Coffee 的韩国结算和依赖 PayPal/Stripe 的 Ko-fi。最终启用了使用 Stripe Connect Express 的 GitHub Sponsors，并确认状态为 `Active`；这与独立注册 Stripe 的要求不同。赞助步骤要求 GitHub 账号，虽然未登录也能打开页面，因此按钮直接标明 GitHub，让用户点击前知道目的地。这些是当时调查结果，不是对支付服务现行政策的断言。

**截图需要体现运行平台（2026-08-29 被拒，08-31 修订）：** Windows 1.0.22 因 `10.1.1 Inaccurate Representation` 被拒，意见称截图显示了非 Windows UI 或设备。八张图中的六张几乎全是 Apple 的真实图标；`window.grab()` 不包含系统边框，无法从画面辨认 Windows。上游还认为应注意当时政策 11.2 对元数据版权或授权的要求。修订版自行创建布局、名称和 43 个图标（`com.homespread.demo.*`），截图包含标题栏，并在拟提交说明末尾加入非关联声明。演示图不再依赖设备、备份或图标缓存，可从仓库重建；只改了元数据，程序包没有改动。

**屏幕截图可能包含其它窗口（2026-08-31）：** 为了保留边框改用 `grabWindow` 后，首次运行因应用没有置前，八张图抓到了用户其它窗口。上游立即删除，没有上传。公开商店图片可能在下架后仍被索引，因此后来脚本先置前，再把捕获的窗口内部与 `window.grab()` 渲染结果比较；不一致就停止且不保存。测试用于防止移除该检查。

**公开页面必须直接核验（2026-09-01）：** 重新提交的 1.0.22 获批，并在 `apps.microsoft.com/detail/9NT54QJ7XQNL` 公开，程序包未改动。Partner Center 的小预览无法区分深色背景上的新旧图块，上游曾据此判断错误。通过 `displaycatalog.mp.microsoft.com/v7.0/products/<StoreID>` 获取两种语言的完整说明和图片尺寸后，确认每种语言四张、尺寸 **1760×911**，是含窗口边框的新版图片；但两份说明均在“已验证环境”/`Verified on` 处结束，缺少拟添加的非关联声明。若要补充该声明，需要另一次仅修改元数据的提交；该记录没有声称已经提交或生效。

## 变更记录

下表保留上游原有条目及当时文件名。旧文件名、测试数量、工具限制和商店状态均按对应日期理解；它们不覆盖上述 macOS 现行规则。

| 日期 | 变更 | 涉及对象 | 原因与证据 |
|---|---|---|---|
| 2026-08-19 | 初始协作配置：7 个 agent、8 个技能 | 全项目 | 初始设置。 |
| 2026-08-19 | 修正核心前提：存在布局写入 API | CLAUDE.md、多份技能 | Phase 1a 确认 `setIconState`，推翻必须重放手势的前提。 |
| 2026-08-19 | 将 `layout-diff-planner` 限定为回退方案，保留文件 | skills/layout-diff-planner | 直接原样写回验证失败后可重新评估的备选，不是当前主路径。 |
| 2026-08-19 | 主要身份键从 `bundleIdentifier` 改为 `displayIdentifier` | skills/homescreen-layout-model、src/ipsm/iconstate.py | 首次真机转储有 79 项（26%）被判为 Unknown；卸载保留项没有 bundle ID。 |
| 2026-08-19 | 备份改用二进制 plist | src/ipsm/backup.py、logging_setup.py | XML plist 截断 `iconModDate` 小数秒，完整性检查因此正确阻止写入。 |
| 2026-08-19 | **原样写回验证通过（REQ-003）**，当时可开始实现编辑 | 上游真机验证 | 309 项，丢失 0、移动 0；当时判定由“完全一致”改为“无丢失或移动”。当前还核对内容变化。 |
| 2026-08-20 | ADR-001 确定 PySide6，并实现编辑 UI | src/ipsm/ui/、app.py、run_app.bat | UI 与设备层共用 Python 对象，避免未知字段在跨语言序列化时丢失。 |
| 2026-08-20 | 增加安装列表与未布局应用提示 | device.list_installed_apps、layout.unplaced_apps | 应用前显示可能被 iOS 回填的应用名称。 |
| 2026-08-20 | 编写四份契约与界面规格 | _workspace/02_contracts/、02_ui-engineer_screen-spec.md | 实现先于契约推进，随后从实际代码提取并记录边界。 |
| 2026-08-20 | 验证图标获取 | cache/icons/ | 287 次请求全部成功，7.4 秒，失败 0。 |
| 2026-08-20 | **编辑到写入流程真机通过** | 上游真机验证 | 应用两次，丢失 0、iOS 新增 0；第二次发送与读回完全一致。 |
| 2026-08-20 | 修复不可见的工具栏文字 | ui/main_window.py STYLE | 只设置深色背景而未设置 QToolButton 文字颜色，保留了 Windows 默认黑字。 |
| 2026-08-20 | PyInstaller 单 exe 分发 | iPhoneScreenManager.spec、src/ipsm/paths.py | 支持没有 Python 的 PC；资料放在 exe 旁，不能放在结束后会清理的 `_MEIPASS`。 |
| 2026-08-20 | 新增分组建文件夹与重命名 | layout.py、ui/tiles.py、ui/canvas.py、ui/main_window.py | 先确认当时 26 个文件夹仅含 `displayName`、`iconLists`、`listType`；重命名写入 `renamed_to`，不修改 raw。 |
| 2026-08-20 | 修复重命名输入框白底白字 | ui/main_window.py STYLE、tests/test_core.py | `QWidget { color }` 只设亮字，未设置 `QLineEdit` 背景；增加实际渲染后的亮度差回归检查。 |
| 2026-08-20 | 文件夹满页时增页，移空时删除文件夹 | layout.py MoveCommand·move·changes、ui/tiles.py | 发送 3 个空文件夹后被 iOS 删除，出现“丢失 3、意外移动 39”的提示；增页与删除都纳入单次拖动的撤销单元。 |
| 2026-08-20 | 在已满文件夹页插入时挤移（SpillCommand） | layout.py SpillCommand·_plan_spill·can_move | 原 `can_move` 因“已满”拒绝从第二页拖到第一页；iPhone 会将最后一项挤到下一页。 |
| 2026-08-20 | 清理文件夹内空页 | layout.py MoveCommand.pruned | 与空文件夹同理，避免系统删除空页造成后续位置偏移。 |
| 2026-08-20 | 主屏幕挤移与空主页清理 | layout.py `_page_family`·`_spill_room`·`_plan_spill`·`_drop_pages`、ui/tiles.py | 用“页面组”共享文件夹和主页规则；`can_move` 必须接收 `dst_index` 才能与 UI 一致判断。 |
| 2026-08-20 | 设置中切换韩语和 English | src/ipsm/i18n.py、translations_en.py、ui/main_window.py SettingsDialog·retranslate、app.py | 原文作为翻译键，缺译时仍有文字；当时内部日志不翻译，便于搜索同一事件；测试检查漏译。 |
| 2026-08-20 | Windows 启动指南自动检查准备状态并提供 Store 入口 | src/ipsm/apple_devices.py、ui/guide.py、ui/main_window.py `_show_guide` | 原来只有点击读取后才看到缺少组件的错误；以 27015 连通性为依据，安装目录只用于选择提示，不据此阻断。 |
| 2026-08-20 | 修复语言下拉列表白底白字 | ui/main_window.py STYLE `QComboBox`·`QComboBox QAbstractItemView`、tests/test_core.py | 展开列表是内部的另一控件，不能只设置组合框背景；加入展开后的亮度对比测试。 |
| 2026-08-20 | **版本 1.0**：集中声明、窗口显示、Windows 构建递增 patch | src/ipsm/version.py、scripts/bump_build.py、build_exe.bat | Python 的 version.py 承担早期全局约定 `shared_vars.h` 的集中版本职责，帮助辨认旧 exe。 |
| 2026-08-20 | 产品改名 **HomeBoard**，名称与副标题分开 | src/ipsm/product.py（新增）、version.py、app.py、device.py、ui/main_window.py、HomeBoard.spec、build_exe.bat、README.md | 按当时商标与商店命名调查，将 `NAME` 与 `TAGLINE` 分开，测试防止在代码多处重复写名称。 |
| 2026-08-20 | 设置页增加 PayPal 赞助按钮 | src/ipsm/product.py `donate_url`、ui/main_window.py SettingsDialog·`_donate`、translations_en.py | 当时按政策 10.8.2 采用无对价赞助；URL 由 product 集中生成，旧 PayPal URL 使用 `no_recurring=1` 关闭定期选项。 |
| 2026-08-20 | **按 GPL-3.0-or-later 发布**，提供原文、告知与关于窗口 | LICENSE、THIRD-PARTY-NOTICES.md、third_party_licenses/、scripts/gen_notices.py、src/ipsm/ui/about.py、paths.bundled、HomeBoard.spec datas | 项目采用与 pymobiledevice3 相容的 GPL 分发；根据安装环境生成第三方告知，避免依赖改变后清单过期。 |
| 2026-08-20 | 隐私说明写入、随 exe 分发并在窗口阅读 | PRIVACY.md、ui/about.py、HomeBoard.spec、tests/test_core.py | 满足当时 Win32 商店要求，测试对照说明与 `settings_path()`。 |
| 2026-08-20 | 建立商店提交清单 | _workspace/05_store-submission-checklist.md | 区分当时已确认的 GPL、赞助、个人账号与待确认的 MSIX 回环、资料目录和 SOURCE_URL。 |
| 2026-08-21 | 窗口出现后再导入设备库 | ui/worker.py `_load_device_layer`、tests/test_core.py | 当时源码启动从 8.5 秒降至 0.36 秒；先创建循环，确保导入期间关闭窗口时 `shutdown()` 有可提交任务的位置。 |
| 2026-08-21 | 增加 Windows 启动画面 | scripts/make_splash.py（新增）、assets/splash.png、HomeBoard.spec `Splash`、app.py `_close_splash` | Python 尚未启动时不能用 Qt 提示，改由 bootloader 显示 Tk 图像。 |
| 2026-08-21 | **从单 exe 改为目录分发**，输出 `dist\HomeBoard\` | HomeBoard.spec `COLLECT`·`exclude_binaries`、build_exe.bat、paths.py、README.md | 实测 21 秒降至 2.3 秒；原先 16.5 秒花在每次解压；MSIX 也使用该目录形式。 |
| 2026-08-21 | 建立 Git 仓库（main，157 个文件） | .gitignore、全项目 | 一个公开地址覆盖源码、隐私与分发入口；排除设备数据，并删除注释中的示例 UDID。 |
| 2026-08-21 | 未布局提示纳入能显示的系统应用 | src/ipsm/device.py `shows_on_home_screen`·`_region_of`·`_home_region`·`list_installed_apps`、tests/test_core.py | 8 月 19 日追加的 4 个应用之一是放大器；仅查询用户应用会漏报，而全算 232 个系统应用会误报 190 个，遂按四项依据保留 40 个候选。 |
| 2026-08-21 | **公开到 github.com/humanlyj/HomeBoard，打 v1.0.14 标签** | 远程 origin、v1.0.14 | 验证匿名访问 LICENSE 和 PRIVACY.md；源码入口不能要求收件者登录才可阅读。提交署名邮箱与 GitHub 账号匹配，关联依据是邮箱而非显示名。 |
| 2026-08-21 | **真机编辑规则检查 15 项通过**，涵盖分组、命名、挤移、清空、写入和恢复 | scripts/verify_edits.py（新增） | 用 35 个文件夹、284 个应用的真实布局检查模型；只有 `--apply` 才写设备，发送最小编辑后恢复。 |
| 2026-08-21 | 按资料用途分目录：图标进 TEMP，备份和日志保留；MSIX 改用文档目录 | src/ipsm/paths.py `is_packaged`·`documents_dir`·`cache_root`、icons.py、ui/worker.py、app.py、PRIVACY.md、README.md、tests/test_core.py | 上游确认 MSIX 安装目录不可写；临时文件可被 Storage Sense 正常清理，不能把备份一并放入。 |
| 2026-08-26 | 商店提交类型确定为“MSIX 或 PWA 应用” | _workspace/05_store-submission-checklist.md §2 | 当时 Partner Center 的“新增产品”分支中，MSIX 由商店以 Microsoft 证书重签；EXE/MSI 则需自己的 CA 证书、Authenticode 签名与安装器，因此选择可通过测试解决剩余问题的 MSIX。 |
| 2026-08-26 | **改名 HomeSpread**，因 HomeBoard 已被占用 | product.py `NAME`、HomeSpread.spec（改名）、build_exe.bat、scripts/keep_data.py·gen_notices.py、__init__.py·app.py 版权行、README.md、PRIVACY.md、THIRD-PARTY-NOTICES.md、tests/test_core.py、CLAUDE.md | 商标约束和名称占用是不同条件；先排除五个已有使用者的候选，仓库实际迁移后再改 SOURCE_URL。 |
| 2026-08-26 | 应对 Defender 误报：exe 加版本资源和图标 | product.py `COPYRIGHT`·`PUBLISHER`、HomeSpread.spec `version=`·`icon=`、tests/test_core.py | 曾两次被标记 `Trojan:Win32/Bearfoos.B!ml`；补充能控制的程序元数据后，新构建扫描与启动通过。云判定按文件哈希，不能据此证明因果。 |
| 2026-08-26 | 写入失败提示点明“受控文件夹访问” | paths.py `_cfa_hint`、translations_en.py、tests/test_core.py | 文件夹权限正常也可能被系统拦截；旧提示建议移到桌面或文档，反而正是该功能默认保护的位置。 |
| 2026-08-26 | **MSIX A、B 验证通过**：松散注册和真实 msix 安装 | scripts/make_msix.py（未改）、packaging/identity.dev.json、.gitignore tools/、_workspace/05_store-submission-checklist.md | A 不能复现只读安装目录；通过 NuGet 构建工具取得 makeappx，未装整个 SDK，使用未签名命名空间完成测试安装。 |
| 2026-08-26 | 修复启动图仍显示旧名称 | assets/splash.png、scripts/make_splash.py `setText`、tests/test_core.py | 绘图源码已读取 product.NAME，问题是旧图片没重生成；将生成时名称写入 PNG tEXt 元数据，再由测试核对。 |
| 2026-08-26 | 应用商店身份并生成上传包 | packaging/identity.json、dist/packages/HomeSpread_1.0.21.0_x64.msix | 从 Partner Center 复制 Product identity，Store ID 为 9NT54QJ7XQNL；删除仍带旧名的 1.0.19 和 1.0.20 包，避免误选上传。 |
| 2026-08-27 | 商店说明与截图改用演示布局 | _workspace/06_store-listing.md（新增）、scripts/make_demo_layout.py·make_screenshots.py（新增）、_workspace/screenshots/、05_store-submission-checklist.md §3、.gitignore | 不公开用户真实应用清单；当时先构造只有 Apple 内置应用的示例，自动生成以便改名后重建；英文图也更换应用名。8 月 31 日进一步改成全自创图标。 |
| 2026-08-28 | 按语言拆分搜索词，将 en-us 的三个韩语词替换为英语 | _workspace/06_store-listing.md §2、05_store-submission-checklist.md §3 | 七个关键词中，前四个含 iPhone/iOS 的词保留，后三个改为英语，避免浪费英语搜索入口。 |
| 2026-08-28 | **赞助从 PayPal 改为 GitHub Sponsors** | product.py `DONATE_ACCOUNT`·`donate_url`（删除 DONATE_ITEM、DONATE_CURRENCY、urlencode）、.github/FUNDING.yml（custom: → github:）、ui/main_window.py、translations_en.py、PRIVACY.md ko/en、README.md 赞助章节、_workspace/05·06、tests/test_core.py | 当时韩国注册账号的 PayPal 限制不因企业账号升级解除；GitHub Sponsors 使用 Stripe Connect Express。测试改为核对支付渠道和 FUNDING.yml 的账号标识，不只核对 URL 外形。 |
| 2026-08-28 | 商店关键词先移出焦点、再保存并刷新核对 | _workspace/05_store-submission-checklist.md §3 | he-select 的可见词条不等于已保存；表单未标记变化时，保存按钮没有发出请求。两次丢失后改为重新读取验证。 |
| 2026-08-31 | **布局、名称和图标全改为自创**，截图保留边框并准备非关联声明 | scripts/make_demo_layout.py（重写）、scripts/make_demo_icons.py（新增）、scripts/make_screenshots.py、_workspace/06 §4·§11、_workspace/05 §3、.gitignore、tests/test_core.py | 1.0.22 因 10.1.1 被拒；Apple 图标加无边框画面容易被理解为 iPhone 屏幕。上游记录的申诉参考数为 12,626 件中 623 件推翻，故选择直接修订元数据，程序包不变。 |
| 2026-08-31 | 核验捕获的确为本应用，否则不保存 | scripts/make_screenshots.py `_grab`·`_difference`、tests/test_core.py | 首次抓到八张其它窗口图，立即删除且未上传；公开图片下架后仍可能留在索引，因此必须检查。 |
| 2026-08-31 | 将测试执行入口移至文件末尾 | tests/test_core.py | `if __name__` 块以 SystemExit 结束，后面两项测试从未定义或执行；原“115 项通过”只覆盖总计 118 项中的 115 项。 |
| 2026-09-01 | **Windows 商店发布**：1.0.22 获批、新八张截图已反映、非关联声明遗漏 | _workspace/05 §3“已通过”、CLAUDE.md | 不依赖小预览判断公开结果，通过 displaycatalog API 核对完整说明与图片尺寸。 |
| 2026-11-13 | 中文 macOS 移植与安全修订 | src/ipsm/、macOS 构建脚本、中文说明和安全报告 | 系统连接、私有资料目录、中文界面、同设备备份、新鲜度检查、写后内容核对与会话写入校验；保留明确确认的恢复通道。真机写回及恢复未执行。 |
| 2026-11-13 | 开发文档与 agent 指南中文化并统一现行约束 | CLAUDE.md、.claude/agents/、相关技能与工作区文档 | 完整保留历史说明、示例和时间线；将已过时的 WDA/手势与 Windows-only 前提限定为历史或有条件的备选研究。 |
