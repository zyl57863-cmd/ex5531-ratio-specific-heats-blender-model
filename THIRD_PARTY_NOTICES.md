# Third-Party Open Source Notices

本文件记录本仓库在模型生成、导出和网页预览过程中实际使用的第三方开源软件。审计范围包括 `build_ex5531_final_model.py`、`deliverables_ex5531_final/preview/index.html`、当前 `.blend/.glb` 文件及其导出结构。

## 1. Blender 5.2.0 LTS

- 用途：创建和保存 `.blend`，执行模型生成脚本，并导出 glTF 2.0/GLB。
- 使用接口：`bpy`、`mathutils.Vector`、Blender内置glTF 2.0导出器。
- 许可证：GNU General Public License（Blender官方说明）。
- 官方项目：https://www.blender.org/
- 官方许可说明：https://developer.blender.org/docs/license
- 分发说明：本仓库不分发Blender可执行程序或其Python模块；使用者需自行安装Blender。Blender官方手册说明，GPL适用于Blender应用本身，并不会自动应用于使用Blender创作的模型或图像。

## 2. Python 3.13.13（Blender内置运行时）

- 用途：运行 `build_ex5531_final_model.py`。
- 使用的标准库：`json`、`math`、`os`。
- 许可证：Python Software Foundation License Version 2。
- 官方许可说明：https://docs.python.org/3.13/license.html
- 分发说明：Python运行时由Blender安装包提供，本仓库不单独分发Python。

## 3. three.js 0.165.0（r165）

- 用途：在 `deliverables_ex5531_final/preview/index.html` 中显示和交互浏览GLB模型。
- 实际模块：
  - `three.module.js`
  - `OrbitControls.js`
  - `GLTFLoader.js`
- 获取方式：网页运行时通过 jsDelivr 从 `three@0.165.0` 加载；仓库未复制three.js源码。
- 许可证：MIT License。
- 官方项目：https://github.com/mrdoob/three.js/tree/r165
- 完整许可证：[`THIRD_PARTY_LICENSES/three.js-MIT.txt`](THIRD_PARTY_LICENSES/three.js-MIT.txt)

## 4. jsDelivr

- 用途：仅作为网页预览器加载three.js ES模块的CDN传输服务。
- 使用地址：`https://cdn.jsdelivr.net/npm/three@0.165.0/`
- 说明：jsDelivr不参与模型生成，且其服务端代码未包含在本仓库中。离线环境下网页预览器需要将three.js模块改为本地托管；`.blend`和`.glb`文件本身不依赖CDN。

## 格式标准，不是随仓库分发的软件依赖

- 模型导出格式为 Khronos glTF 2.0/GLB。
- 当前GLB使用 `KHR_materials_transmission` 和 `KHR_materials_ior` 材质扩展。
- 这些是格式扩展标识，不代表仓库嵌入了额外第三方运行库。

## 明确未使用或未打包的项目

- 当前GLB没有启用Draco压缩或MeshOptimizer扩展。Blender日志中显示相关库“可用”不等于本次导出实际使用。
- 仓库和GLB没有打包外部照片、第三方纹理图片、HDRI、字体文件、音频或下载的三维模型。
- 用户提供的实物参考照片仅用于人工观察，不随仓库发布。
- 网页CSS中列出的 `Segoe UI`、`Microsoft YaHei` 是系统字体回退名称，仓库不包含字体文件。
- PASCO、PASPORT及其他可能的品牌名称仅作为设备类型和接口布局的描述性参考；相关商标归其各自权利人所有。本仓库未包含官方商标图片，也不表示获得品牌方认可。

## 项目自身内容

本文件只记录第三方项目，不为本仓库自身的生成脚本、模型、渲染图或文档选择许可证，也不改变这些内容原有的权利状态。
