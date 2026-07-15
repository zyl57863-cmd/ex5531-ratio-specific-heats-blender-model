# EX5531 Ratio of Specific Heats Blender Model

公开的 EX5531/TD8572A 空气比热容比实验装置 Blender 模型，包含实验主机、V形铸铁底座、玻璃比例管、活塞和质量拨片、压力传感器、PASCO风格数据接口、软管与数据线连接结构。

![模型总览](deliverables_ex5531_final/previews/preview_system_overview.png)

## 仓库内容

- `build_ex5531_final_model.py`：可重复生成模型、预览图和验证报告的 Blender Python 脚本。
- `deliverables_ex5531_final/EX5531_TD8572A_ratio_specific_heats_final.blend`：可直接编辑和预览的 Blender 文件。
- `deliverables_ex5531_final/EX5531_TD8572A_ratio_specific_heats_final.glb`：便于共享和导入其他软件的 GLB 文件。
- `deliverables_ex5531_final/verification_report.json`：尺寸、位置、连接关系和模型结构的自动验证报告。
- `deliverables_ex5531_final/glb_export_audit.json`：GLB 导出结构检查结果。
- `deliverables_ex5531_final/previews/`：多角度及局部细节预览图。
- `deliverables_ex5531_final/preview/index.html`：本地 GLB 网页预览器。

## 当前模型重点

- 玻璃管正面包含 80、70、60、50、40、30、20、10、0 九级编号刻度。
- 刻度数字贴合玻璃管曲面并保持正常字重。
- 活塞Z向高度约 26.4 mm。
- PistonRod总长约 277.2 mm，并与上拨片顶面齐平。
- 包含精细化数字输入、模拟输入、PASPORT和BNC输出接口。

## PowerShell预览

Blender已加入 `PATH` 时：

```powershell
blender "$PWD\deliverables_ex5531_final\EX5531_TD8572A_ratio_specific_heats_final.blend"
```

使用本机当前Blender安装路径：

```powershell
& 'D:\game\steam\steamapps\common\Blender\blender.exe' "$PWD\deliverables_ex5531_final\EX5531_TD8572A_ratio_specific_heats_final.blend"
```

## 重新生成模型

```powershell
& 'D:\game\steam\steamapps\common\Blender\blender.exe' --background --python "$PWD\build_ex5531_final_model.py"
```

生成脚本使用自身所在目录作为项目根目录，不依赖原作者的本机路径。当前交付文件由 Blender 5.2.0 LTS 生成。

## 验证

```powershell
$report = Get-Content -Raw "$PWD\deliverables_ex5531_final\verification_report.json" | ConvertFrom-Json
$report.all_checks_passed
```

预期输出为 `True`。
