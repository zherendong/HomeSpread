# 第三方组件与许可证

本文件保留上游 Windows 构建环境的 92 个组件快照，包名、版本和许可元数据不因汉化而改写。各行链接指向 `third_party_licenses/` 中的法律原文；没有原文链接的条目不表示没有许可要求。

当前 macOS 版使用独立的 `requirements-macos.lock`，构建时由 `scripts/prepare_macos.py` 生成对应版本的清单和原文，随 `.app` 分发。不能用此 Windows 快照推断 macOS 的依赖版本。

HomeSpread 声明采用 GPL-3.0-or-later，第三方组件保留各自许可。项目法律原文见 [LICENSE](LICENSE)，中文阅读说明见 [LICENSE.zh-CN.md](LICENSE.zh-CN.md)。

Windows 构建环境可运行 `scripts/gen_notices.py` 重新生成本清单；该脚本读取实际安装版本，并会更新原文目录，不应在其它环境运行后把结果误称为 Windows 历史快照。

| 组件 | 版本 | 许可元数据 | 原文 | 来源 |
|---|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | [annotated-doc-0.0.5.txt](third_party_licenses/annotated-doc-0.0.5.txt) | [https://github.com/fastapi/annotated-doc](https://github.com/fastapi/annotated-doc) |
| annotated-types | 0.8.0 | MIT | [annotated-types-0.8.0.txt](third_party_licenses/annotated-types-0.8.0.txt) | [https://github.com/annotated-types/annotated-types](https://github.com/annotated-types/annotated-types) |
| ansicon | 1.89.0 | Mozilla Public License 2.0 (MPL 2.0) | [ansicon-1.89.0.txt](third_party_licenses/ansicon-1.89.0.txt) | [https://github.com/Rockhopper-Technologies/ansicon](https://github.com/Rockhopper-Technologies/ansicon) |
| anyio | 4.14.2 | MIT | [anyio-4.14.2.txt](third_party_licenses/anyio-4.14.2.txt) | [https://github.com/agronholm/anyio](https://github.com/agronholm/anyio) |
| arrow | 1.4.0 | Apache Software License | [arrow-1.4.0.txt](third_party_licenses/arrow-1.4.0.txt) | [https://github.com/arrow-py/arrow](https://github.com/arrow-py/arrow) |
| asn1 | 3.3.0 | MIT | [asn1-3.3.0.txt](third_party_licenses/asn1-3.3.0.txt) | [https://github.com/andrivet/python-asn1](https://github.com/andrivet/python-asn1) |
| asttokens | 3.0.2 | Apache 2.0 | [asttokens-3.0.2.txt](third_party_licenses/asttokens-3.0.2.txt) | [https://github.com/gristlabs/asttokens](https://github.com/gristlabs/asttokens) |
| blessed | 1.48.0 | MIT | [blessed-1.48.0.txt](third_party_licenses/blessed-1.48.0.txt) | [https://github.com/jquast/blessed](https://github.com/jquast/blessed) |
| bpylist2 | 4.1.1 | MIT License | — | [https://github.com/parabolala/bpylist2](https://github.com/parabolala/bpylist2) |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | [certifi-2026.7.22.txt](third_party_licenses/certifi-2026.7.22.txt) | [https://github.com/certifi/python-certifi](https://github.com/certifi/python-certifi) |
| cffi | 2.1.1 | MIT-0 | [cffi-2.1.1.txt](third_party_licenses/cffi-2.1.1.txt) | [https://github.com/python-cffi/cffi](https://github.com/python-cffi/cffi) |
| charset-normalizer | 3.5.1 | MIT | [charset-normalizer-3.5.1.txt](third_party_licenses/charset-normalizer-3.5.1.txt) | — |
| click | 8.4.2 | BSD-3-Clause | [click-8.4.2.txt](third_party_licenses/click-8.4.2.txt) | [https://github.com/pallets/click/](https://github.com/pallets/click/) |
| colorama | 0.4.6 | BSD License | [colorama-0.4.6.txt](third_party_licenses/colorama-0.4.6.txt) | [https://github.com/tartley/colorama](https://github.com/tartley/colorama) |
| coloredlogs | 15.0.1 | MIT License | [coloredlogs-15.0.1.txt](third_party_licenses/coloredlogs-15.0.1.txt) | [https://coloredlogs.readthedocs.io](https://coloredlogs.readthedocs.io) |
| construct | 2.10.70 | MIT License | [construct-2.10.70.txt](third_party_licenses/construct-2.10.70.txt) | [http://construct.readthedocs.org](http://construct.readthedocs.org) |
| construct-typing | 0.8.1 | MIT | [construct-typing-0.8.1.txt](third_party_licenses/construct-typing-0.8.1.txt) | [https://github.com/timrid/construct-typing](https://github.com/timrid/construct-typing) |
| cryptography | 50.0.0 | Apache-2.0 OR BSD-3-Clause | [cryptography-50.0.0.txt](third_party_licenses/cryptography-50.0.0.txt) | [https://github.com/pyca/cryptography](https://github.com/pyca/cryptography) |
| daemonize | 2.5.0 | MIT License | [daemonize-2.5.0.txt](third_party_licenses/daemonize-2.5.0.txt) | [https://github.com/thesharp/daemonize](https://github.com/thesharp/daemonize) |
| developer_disk_image | 0.3.0 | GNU General Public License v3 or later (GPLv3+) | — | [https://github.com/doronz88/DeveloperDiskImage](https://github.com/doronz88/DeveloperDiskImage) |
| editor | 1.8.0 | MIT | [editor-1.8.0.txt](third_party_licenses/editor-1.8.0.txt) | [https://github.com/rec/editor](https://github.com/rec/editor) |
| enum-compat | 0.0.3 | MIT | — | [https://github.com/jstasiak/enum-compat](https://github.com/jstasiak/enum-compat) |
| executing | 2.2.1 | MIT License | [executing-2.2.1.txt](third_party_licenses/executing-2.2.1.txt) | [https://github.com/alexmojaki/executing](https://github.com/alexmojaki/executing) |
| fastapi | 0.141.1 | MIT | [fastapi-0.141.1.txt](third_party_licenses/fastapi-0.141.1.txt) | [https://github.com/fastapi/fastapi](https://github.com/fastapi/fastapi) |
| gpxpy | 1.6.2 | Apache License, Version 2.0 | [gpxpy-1.6.2.txt](third_party_licenses/gpxpy-1.6.2.txt) | [https://github.com/tkrajina/gpxpy](https://github.com/tkrajina/gpxpy) |
| h11 | 0.16.0 | MIT License | [h11-0.16.0.txt](third_party_licenses/h11-0.16.0.txt) | [https://github.com/python-hyper/h11](https://github.com/python-hyper/h11) |
| hexdump | 3.3 | Public Domain | — | [https://bitbucket.org/techtonik/hexdump/](https://bitbucket.org/techtonik/hexdump/) |
| humanfriendly | 10.0 | MIT License | [humanfriendly-10.0.txt](third_party_licenses/humanfriendly-10.0.txt) | [https://humanfriendly.readthedocs.io](https://humanfriendly.readthedocs.io) |
| hyperframe | 6.1.0 | MIT License | [hyperframe-6.1.0.txt](third_party_licenses/hyperframe-6.1.0.txt) | [https://github.com/python-hyper/hyperframe/](https://github.com/python-hyper/hyperframe/) |
| idna | 3.19 | BSD-3-Clause | [idna-3.19.md](third_party_licenses/idna-3.19.md) | [https://github.com/kjd/idna](https://github.com/kjd/idna) |
| ifaddr | 0.2.0 | MIT License | [ifaddr-0.2.0.txt](third_party_licenses/ifaddr-0.2.0.txt) | [https://github.com/pydron/ifaddr](https://github.com/pydron/ifaddr) |
| inquirer3 | 0.6.1 | MIT License | [inquirer3-0.6.1.txt](third_party_licenses/inquirer3-0.6.1.txt) | [https://github.com/guysalt/python-inquirer3](https://github.com/guysalt/python-inquirer3) |
| ipython | 9.16.1 | BSD-3-Clause | [ipython-9.16.1.rst](third_party_licenses/ipython-9.16.1.rst) | [https://ipython.org](https://ipython.org) |
| ipython_pygments_lexers | 1.1.1 | BSD License | [ipython_pygments_lexers-1.1.1.txt](third_party_licenses/ipython_pygments_lexers-1.1.1.txt) | [https://github.com/ipython/ipython-pygments-lexers](https://github.com/ipython/ipython-pygments-lexers) |
| jedi | 0.20.0 | MIT License | [jedi-0.20.0.txt](third_party_licenses/jedi-0.20.0.txt) | [https://github.com/davidhalter/jedi](https://github.com/davidhalter/jedi) |
| jinxed | 2.1.0 | Mozilla Public License 2.0 (MPL 2.0) | [jinxed-2.1.0.txt](third_party_licenses/jinxed-2.1.0.txt) | [https://github.com/Rockhopper-Technologies/jinxed](https://github.com/Rockhopper-Technologies/jinxed) |
| markdown-it-py | 4.2.0 | MIT License | [markdown-it-py-4.2.0.txt](third_party_licenses/markdown-it-py-4.2.0.txt) | [https://github.com/executablebooks/markdown-it-py](https://github.com/executablebooks/markdown-it-py) |
| matplotlib-inline | 0.2.2 | BSD-3-Clause | [matplotlib-inline-0.2.2.txt](third_party_licenses/matplotlib-inline-0.2.2.txt) | [https://github.com/ipython/matplotlib-inline](https://github.com/ipython/matplotlib-inline) |
| mdurl | 0.1.2 | MIT License | [mdurl-0.1.2.txt](third_party_licenses/mdurl-0.1.2.txt) | [https://github.com/executablebooks/mdurl](https://github.com/executablebooks/mdurl) |
| opack2 | 0.0.1 | GNU General Public License v3 or later (GPLv3+) | [opack2-0.0.1.txt](third_party_licenses/opack2-0.0.1.txt) | [https://github.com/doronz88/opack2](https://github.com/doronz88/opack2) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [packaging-26.3.txt](third_party_licenses/packaging-26.3.txt) | [https://github.com/pypa/packaging](https://github.com/pypa/packaging) |
| parameter-decorators | 0.0.2 | GNU GENERAL PUBLIC LICENSE | [parameter-decorators-0.0.2.txt](third_party_licenses/parameter-decorators-0.0.2.txt) | [https://github.com/matan1008/parameter-decorators](https://github.com/matan1008/parameter-decorators) |
| parso | 0.8.7 | MIT License | [parso-0.8.7.txt](third_party_licenses/parso-0.8.7.txt) | [https://github.com/davidhalter/parso](https://github.com/davidhalter/parso) |
| pillow | 12.3.0 | MIT-CMU | [pillow-12.3.0.txt](third_party_licenses/pillow-12.3.0.txt) | [https://python-pillow.github.io](https://python-pillow.github.io) |
| plumbum | 2.0.2 | MIT | [plumbum-2.0.2.txt](third_party_licenses/plumbum-2.0.2.txt) | [https://github.com/tomerfiliba/plumbum](https://github.com/tomerfiliba/plumbum) |
| prompt_toolkit | 3.0.53 | BSD License | [prompt_toolkit-3.0.53.txt](third_party_licenses/prompt_toolkit-3.0.53.txt) | [https://github.com/prompt-toolkit/python-prompt-toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) |
| psutil | 7.2.2 | BSD-3-Clause | [psutil-7.2.2.txt](third_party_licenses/psutil-7.2.2.txt) | [https://github.com/giampaolo/psutil](https://github.com/giampaolo/psutil) |
| pure_eval | 0.2.3 | MIT License | [pure_eval-0.2.3.txt](third_party_licenses/pure_eval-0.2.3.txt) | [http://github.com/alexmojaki/pure_eval](http://github.com/alexmojaki/pure_eval) |
| pyasn1 | 0.6.4 | BSD-2-Clause | [pyasn1-0.6.4.rst](third_party_licenses/pyasn1-0.6.4.rst) | [https://github.com/pyasn1/pyasn1](https://github.com/pyasn1/pyasn1) |
| pycparser | 3.0 | BSD-3-Clause | [pycparser-3.0.txt](third_party_licenses/pycparser-3.0.txt) | [https://github.com/eliben/pycparser](https://github.com/eliben/pycparser) |
| pycrashreport | 2.0.0 | GNU General Public License v3 or later (GPLv3+) | [pycrashreport-2.0.0.txt](third_party_licenses/pycrashreport-2.0.0.txt) | [https://github.com/doronz88/pycrashreport](https://github.com/doronz88/pycrashreport) |
| pydantic | 2.13.4 | MIT | [pydantic-2.13.4.txt](third_party_licenses/pydantic-2.13.4.txt) | [https://github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) |
| pydantic_core | 2.46.4 | MIT | [pydantic_core-2.46.4.txt](third_party_licenses/pydantic_core-2.46.4.txt) | [https://github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) |
| Pygments | 2.21.0 | BSD-2-Clause | [Pygments-2.21.0.txt](third_party_licenses/Pygments-2.21.0.txt) | [https://pygments.org](https://pygments.org) |
| pygnuutils | 0.1.1 | GNU General Public License v3 or later (GPLv3+) | [pygnuutils-0.1.1.txt](third_party_licenses/pygnuutils-0.1.1.txt) | [https://github.com/matan1008/pygnuutils](https://github.com/matan1008/pygnuutils) |
| pykdebugparser | 1.2.8 | MIT License | [pykdebugparser-1.2.8.txt](third_party_licenses/pykdebugparser-1.2.8.txt) | [https://github.com/matan1008/pykdebugparser](https://github.com/matan1008/pykdebugparser) |
| pymobiledevice3 | 10.9.0 | GPL-3.0-or-later | [pymobiledevice3-10.9.0.txt](third_party_licenses/pymobiledevice3-10.9.0.txt) | [https://github.com/doronz88/pymobiledevice3](https://github.com/doronz88/pymobiledevice3) |
| pyreadline3 | 3.5.6 | BSD License | [pyreadline3-3.5.6.md](third_party_licenses/pyreadline3-3.5.6.md) | [https://github.com/pyreadline3/pyreadline3](https://github.com/pyreadline3/pyreadline3) |
| PySide6_Essentials | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | [PySide6_Essentials-6.11.2.txt](third_party_licenses/PySide6_Essentials-6.11.2.txt) | [https://pyside.org](https://pyside.org) |
| python-dateutil | 2.9.0.post0 | BSD License / Apache Software License | [python-dateutil-2.9.0.post0.txt](third_party_licenses/python-dateutil-2.9.0.post0.txt) | [https://github.com/dateutil/dateutil](https://github.com/dateutil/dateutil) |
| python-pcapng | 2.1.1 | Apache Software License | [python-pcapng-2.1.1.txt](third_party_licenses/python-pcapng-2.1.1.txt) | [https://github.com/rshk/python-pcapng](https://github.com/rshk/python-pcapng) |
| pytun-pmd3 | 3.0.3 | GNU General Public License v3 or later (GPLv3+) | [pytun-pmd3-3.0.3.txt](third_party_licenses/pytun-pmd3-3.0.3.txt) | [https://github.com/doronz88/pytun-pmd3](https://github.com/doronz88/pytun-pmd3) |
| pyusb | 1.3.1 | BSD License | [pyusb-1.3.1.txt](third_party_licenses/pyusb-1.3.1.txt) | [https://pyusb.github.io/pyusb](https://pyusb.github.io/pyusb) |
| pywin32 | 312 | Python Software Foundation License | [pywin32-312.txt](third_party_licenses/pywin32-312.txt) | [https://github.com/mhammond/pywin32](https://github.com/mhammond/pywin32) |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | [pywin32-ctypes-0.2.3.txt](third_party_licenses/pywin32-ctypes-0.2.3.txt) | [https://github.com/enthought/pywin32-ctypes](https://github.com/enthought/pywin32-ctypes) |
| qh3 | 1.9.4 | BSD License | [qh3-1.9.4.txt](third_party_licenses/qh3-1.9.4.txt) | [https://github.com/jawah/qh3](https://github.com/jawah/qh3) |
| questionary | 2.1.1 | MIT License | [questionary-2.1.1.txt](third_party_licenses/questionary-2.1.1.txt) | [https://github.com/tmbo/questionary](https://github.com/tmbo/questionary) |
| readchar | 4.2.2 | MIT License | — | [https://pypi.org/project/readchar](https://pypi.org/project/readchar) |
| requests | 2.34.2 | Apache Software License | [requests-2.34.2.txt](third_party_licenses/requests-2.34.2.txt) | [https://github.com/psf/requests](https://github.com/psf/requests) |
| rich | 15.0.0 | MIT License | [rich-15.0.0.txt](third_party_licenses/rich-15.0.0.txt) | [https://github.com/Textualize/rich](https://github.com/Textualize/rich) |
| runs | 1.3.0 | MIT | — | — |
| shellingham | 1.5.4 | ISC License (ISCL) | [shellingham-1.5.4.txt](third_party_licenses/shellingham-1.5.4.txt) | [https://github.com/sarugaku/shellingham](https://github.com/sarugaku/shellingham) |
| shiboken6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | [shiboken6-6.11.2.txt](third_party_licenses/shiboken6-6.11.2.txt) | [https://pyside.org](https://pyside.org) |
| six | 1.17.0 | MIT License | [six-1.17.0.txt](third_party_licenses/six-1.17.0.txt) | [https://github.com/benjaminp/six](https://github.com/benjaminp/six) |
| srptools | 1.0.1 | BSD License | [srptools-1.0.1.txt](third_party_licenses/srptools-1.0.1.txt) | [https://github.com/idlesign/srptools](https://github.com/idlesign/srptools) |
| stack-data | 0.6.3 | MIT License | [stack-data-0.6.3.txt](third_party_licenses/stack-data-0.6.3.txt) | [http://github.com/alexmojaki/stack_data](http://github.com/alexmojaki/stack_data) |
| starlette | 1.6.0 | BSD-3-Clause | [starlette-1.6.0.md](third_party_licenses/starlette-1.6.0.md) | [https://github.com/Kludex/starlette](https://github.com/Kludex/starlette) |
| termcolor | 3.3.0 | MIT | [termcolor-3.3.0.txt](third_party_licenses/termcolor-3.3.0.txt) | [https://github.com/termcolor/termcolor](https://github.com/termcolor/termcolor) |
| tqdm | 4.70.0 | MPL-2.0 AND MIT | — | [https://tqdm.github.io](https://tqdm.github.io) |
| traitlets | 5.16.1 | BSD License | [traitlets-5.16.1.txt](third_party_licenses/traitlets-5.16.1.txt) | [https://github.com/ipython/traitlets](https://github.com/ipython/traitlets) |
| typer | 0.27.1 | MIT | [typer-0.27.1.txt](third_party_licenses/typer-0.27.1.txt) | [https://github.com/fastapi/typer](https://github.com/fastapi/typer) |
| typer-injector | 0.3.0 | MIT | [typer-injector-0.3.0.txt](third_party_licenses/typer-injector-0.3.0.txt) | [https://github.com/BenjyWiener/typer-injector](https://github.com/BenjyWiener/typer-injector) |
| typing-inspection | 0.4.4 | MIT | [typing-inspection-0.4.4.txt](third_party_licenses/typing-inspection-0.4.4.txt) | [https://github.com/pydantic/typing-inspection](https://github.com/pydantic/typing-inspection) |
| typing_extensions | 4.16.0 | PSF-2.0 | [typing_extensions-4.16.0.txt](third_party_licenses/typing_extensions-4.16.0.txt) | [https://github.com/python/typing_extensions](https://github.com/python/typing_extensions) |
| tzdata | 2026.3 | Apache-2.0 | [tzdata-2026.3.txt](third_party_licenses/tzdata-2026.3.txt) | [https://github.com/python/tzdata](https://github.com/python/tzdata) |
| urllib3 | 2.7.0 | MIT | [urllib3-2.7.0.txt](third_party_licenses/urllib3-2.7.0.txt) | — |
| uvicorn | 0.52.3 | BSD-3-Clause | [uvicorn-0.52.3.md](third_party_licenses/uvicorn-0.52.3.md) | [https://uvicorn.dev/](https://uvicorn.dev/) |
| wcwidth | 0.8.2 | MIT | [wcwidth-0.8.2.txt](third_party_licenses/wcwidth-0.8.2.txt) | [https://github.com/jquast/wcwidth](https://github.com/jquast/wcwidth) |
| wsproto | 1.3.2 | MIT | [wsproto-1.3.2.txt](third_party_licenses/wsproto-1.3.2.txt) | [https://github.com/python-hyper/wsproto/](https://github.com/python-hyper/wsproto/) |
| xmod | 1.10.0 | MIT | [xmod-1.10.0.txt](third_party_licenses/xmod-1.10.0.txt) | [https://github.com/rec/xmod](https://github.com/rec/xmod) |
| xonsh | 0.24.1 | BSD 2-Clause License | [xonsh-0.24.1.txt](third_party_licenses/xonsh-0.24.1.txt) | [https://xon.sh](https://xon.sh) |
| zeroconf | 0.150.0 | LGPL-2.1-or-later | [zeroconf-0.150.0.txt](third_party_licenses/zeroconf-0.150.0.txt) | [https://github.com/python-zeroconf/python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) |

上游清单排除了只用于构建 exe 的工具：altgraph、pefile、pip、pyinstaller、pyinstaller-hooks-contrib、setuptools、wheel。
