# -*- coding: utf-8 -*-
##--------------------------------------------------------------------------
##
## 脚本名称 : BonMeshTool
## 作者    : 杨陶
## URL     : https://github.com/JaimeTao/BonModellingTool/tree/main
##E-mail   : taoyangfan@qq.com
## 更新时间 : 2024/06/27
## 添加功能 : 存储所选边、选择存储边。优化快速选择工具、选择存储边残留选择状态的bug
## 更新时间 : 2024/07/02-版本01
## 添加功能 : 间隔选择工具添加Loop功能
## 更新时间 : 2024/07/02-版本02
## 添加功能 : 窗口底部添加添加自动更新和保存窗口（占位）按钮
## 更新时间 : 2024/07/02-版本03
## 添加功能 : 添加git pull更新功能
## 更新时间 : 2024/07/05-版本01
## 添加功能 : 折叠窗口字体从像素改为百分比
## 更新时间 : 2024/07/05-版本02
## 添加功能 : 优化脚本
## 更新时间 : 2024/07/05-版本01
## 添加功能 : 把间隔选择改为交互式实时预览
## 更新时间 : 2024/07/16-版本01
## 添加功能 : 修复存储边和读取存储边bug
## 更新时间 : 2025/09/10-版本01
## 添加功能 : 添加平均化边长功能
## 更新时间 : 2025/11/10-版本01
## 添加功能 : 对间隔选择工具做了是否开启对称的判断
## 更新时间 : 2026/4/15-版本01
## 添加功能 : 新增清理工具，用于清理重合的重复模型和零面积面
##--------------------------------------------------------------------------
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2.QtWidgets import *
from PySide2.QtCore import *
import maya.cmds as cmds
import maya.mel as mel
import subprocess
import os
import re

# ---- Symmetry detection helpers ----
def _mt_symmetry_on():
    try:
        comp_sym_on = cmds.symmetricModelling(query=True, symmetry=True)
    except Exception:
        comp_sym_on = False

    any_axis_on = False
    for flag in ("topology", "objectX", "objectY", "objectZ", "worldX", "worldY", "worldZ"):
        try:
            val = cmds.symmetricModelling(query=True, **{flag: True})
            if isinstance(val, bool) and val:
                any_axis_on = True
        except Exception:
            pass
    return bool(comp_sym_on or any_axis_on)

def _legacy_symmetry_on():
    for var in ("symmetry", "modelingToolkitSymmetry", "polySymmetryEnabled"):
        try:
            if cmds.optionVar(exists=var):
                val = cmds.optionVar(q=var)
                if isinstance(val, (int, bool)) and int(val) != 0:
                    return True
        except Exception:
            pass
    try:
        ctx = cmds.currentCtx()
        if ctx:
            for attr in ("symmetry", "symmetryEnabled"):
                try:
                    val = cmds.contextInfo(ctx, q=True, **{attr: True})
                    if isinstance(val, (int, bool)) and int(val) != 0:
                        return True
                except Exception:
                    pass
    except Exception:
        pass
    return False

def is_symmetry_on():
    return _mt_symmetry_on() or _legacy_symmetry_on()


class CollapsibleSection(QWidget):
    def __init__(self, title="", parent=None):
        super(CollapsibleSection, self).__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.toggle_button = QToolButton(text=title, checkable=True, checked=True)
        self.toggle_button.setStyleSheet("QToolButton { border: none; padding-top: 0.2em; padding-bottom: 0.2em; color: #bbbbbb; font-weight: bold; background-color: #3c3c3c; font-size: 1.1em;}")
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.clicked.connect(self.toggle)

        self.content_area = QWidget()
        self.content_area.setLayout(QVBoxLayout())
        self.content_area.layout().setAlignment(Qt.AlignTop)
        self.content_area.layout().setSpacing(2)
        self.content_area.layout().setContentsMargins(2, 2, 2, 2)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.layout().addWidget(self.toggle_button)
        self.layout().addWidget(self.content_area)
        self.content_area.setVisible(self.toggle_button.isChecked())
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")

    def toggle(self):
        self.toggle_button.setArrowType(Qt.DownArrow if not self.toggle_button.isChecked() else Qt.RightArrow)
        if self.content_area.isVisible():
            self.toggle_animation.setDuration(150)
            self.toggle_animation.setStartValue(self.content_area.sizeHint().height())
            self.toggle_animation.setEndValue(0)
            self.toggle_animation.start()
            self.content_area.setVisible(False)
        else:
            self.content_area.setVisible(True)
            self.toggle_animation.setDuration(150)
            self.toggle_animation.setStartValue(0)
            self.toggle_animation.setEndValue(self.content_area.sizeHint().height())
            self.toggle_animation.start()

    def addWidget(self, widget):
        self.content_area.layout().addWidget(widget)


class BonMeshToolUI(MayaQWidgetDockableMixin, QWidget):
    def __init__(self, parent=None):
        super(BonMeshToolUI, self).__init__(parent)
        self.window_name = 'BonMeshToolUI'
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle('BonMeshTool')
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.setup_dirs()
        
        self.setMinimumWidth(250)
        self.setMinimumHeight(450)

        self.restore_window_settings()

        # UV Section
        uv_section = CollapsibleSection("重命名并删除多余UV集！")
        rename_widget = QWidget()
        rename_layout = QHBoxLayout()
        self.rename_button = QPushButton('重命名')
        self.rename_line_edit = QLineEdit('map1')
        rename_layout.addWidget(self.rename_button)
        rename_layout.addWidget(self.rename_line_edit)
        rename_widget.setLayout(rename_layout)
        uv_section.addWidget(rename_widget)
        self.layout().addWidget(uv_section)
        self.rename_button.clicked.connect(self.RenameUVSetCmd)

        # Triangle Section
        triangle_section = CollapsibleSection("修改三角形分割方式")
        self.display_triangle_checkbox = QCheckBox('显示三角分割')
        triangle_section.addWidget(self.display_triangle_checkbox)
        self.display_triangle_checkbox.stateChanged.connect(self.DisplayTriangle)
        
        triangle_row1_widget = QWidget()
        triangle_row1_layout = QHBoxLayout()
        maya_button = QPushButton('切换到maya三角分割')
        unity_button = QPushButton('切换到unity三角分割')
        maya_button.clicked.connect(self.mayaTriangleCmd)
        unity_button.clicked.connect(self.unityTriangleCmd)
        triangle_row1_layout.addWidget(maya_button)
        triangle_row1_layout.addWidget(unity_button)
        triangle_row1_widget.setLayout(triangle_row1_layout)
        triangle_section.addWidget(triangle_row1_widget)

        triangle_row2_widget = QWidget()
        triangle_row2_layout = QHBoxLayout()
        unlock_button = QPushButton('解锁法线')
        soft_button = QPushButton('软边')
        hard_button = QPushButton('硬边')
        triangle_row2_layout.addWidget(unlock_button)
        triangle_row2_layout.addWidget(soft_button)
        triangle_row2_layout.addWidget(hard_button)
        unlock_button.clicked.connect(self.UnlockNormalCmd)
        soft_button.clicked.connect(self.SoftenEdgeCmd)
        hard_button.clicked.connect(self.HardenEdgeCmd)
        triangle_row2_widget.setLayout(triangle_row2_layout)
        triangle_section.addWidget(triangle_row2_widget)
        self.layout().addWidget(triangle_section)

        # Selection Section
        selection_section = CollapsibleSection("快速选择工具")
        selection_widget = QWidget()
        selection_layout = QVBoxLayout()
        first_row_layout = QHBoxLayout()
        select_uv_edges_button = QPushButton('选择UV边界')
        select_hard_edges_button = QPushButton('选择硬边')
        first_row_layout.addWidget(select_uv_edges_button)
        first_row_layout.addWidget(select_hard_edges_button)
        second_row_layout = QHBoxLayout()
        store_edges_button = QPushButton('存储选择边')
        select_stored_edges_button = QPushButton('选择存储边')
        second_row_layout.addWidget(store_edges_button)
        second_row_layout.addWidget(select_stored_edges_button)
        selection_layout.addLayout(first_row_layout)
        selection_layout.addLayout(second_row_layout)
        selection_widget.setLayout(selection_layout)
        selection_section.addWidget(selection_widget)
        self.layout().addWidget(selection_section)
        select_uv_edges_button.clicked.connect(self.SelUVBrodenEdgeCmd)
        select_hard_edges_button.clicked.connect(self.SelHardenEdgeCmd)
        store_edges_button.clicked.connect(self.store_edges)
        select_stored_edges_button.clicked.connect(self.select_edges)

        # --- Updated Transfer Section ---
        transfer_section = CollapsibleSection("传递属性工具")
        transfer_grid_widget = QWidget()
        transfer_grid_layout = QGridLayout()
        transfer_grid_layout.setSpacing(4)

        btn_pos_uv = QPushButton('位置toUV')
        btn_uv_pos = QPushButton('UVto位置')
        btn_border = QPushButton('边界to边界')
        btn_mirror = QPushButton('表情镜像')
        
        # 统一设置按钮高度
        for btn in [btn_pos_uv, btn_uv_pos, btn_border, btn_mirror]:
            btn.setMinimumHeight(28)

        # 2x2 布局: (row, column)
        transfer_grid_layout.addWidget(btn_pos_uv, 0, 0)
        transfer_grid_layout.addWidget(btn_uv_pos, 0, 1)
        transfer_grid_layout.addWidget(btn_border, 1, 0)
        transfer_grid_layout.addWidget(btn_mirror, 1, 1)

        transfer_grid_widget.setLayout(transfer_grid_layout)
        transfer_section.addWidget(transfer_grid_widget)
        self.layout().addWidget(transfer_section)

        btn_pos_uv.clicked.connect(self.TranPositoUVCmd)
        btn_uv_pos.clicked.connect(self.TranUVtoPosiCmd)
        btn_border.clicked.connect(self.TranPositoBordenECmd)
        btn_mirror.clicked.connect(self.ExpressionMirrorCmd)

        # Interval Selection Section
        interval_section = CollapsibleSection("间隔选择工具")
        slider_widget = QWidget()
        slider_layout = QVBoxLayout()
        interval_slider_layout = QHBoxLayout()
        self.Ring_value_label = QLabel("Ring间隔数: %d" % 1)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0); self.slider.setMaximum(20); self.slider.setValue(1)
        interval_slider_layout.addWidget(self.Ring_value_label)
        interval_slider_layout.addWidget(self.slider)
        self.slider.valueChanged.connect(self.Ring_slider_value_changed)
        slider_layout.addLayout(interval_slider_layout)
        loop_slider_layout = QHBoxLayout()
        self.loop_value_label = QLabel("loop间隔数: %d" % 0)
        self.loop_slider = QSlider(Qt.Horizontal)
        self.loop_slider.setMinimum(0); self.loop_slider.setMaximum(20); self.loop_slider.setValue(0)
        loop_slider_layout.addWidget(self.loop_value_label)
        loop_slider_layout.addWidget(self.loop_slider)
        self.loop_slider.valueChanged.connect(self.loop_slider_value_changed)
        slider_layout.addLayout(loop_slider_layout)
        slider_widget.setLayout(slider_layout)
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        to_rings_button = QPushButton('间隔选择')
        Extend_to_Ring_button = QPushButton('Ring延伸')
        Extend_to_Loops_button = QPushButton('Loop延伸')
        button_layout.addWidget(to_rings_button); button_layout.addWidget(Extend_to_Ring_button); button_layout.addWidget(Extend_to_Loops_button)
        button_widget.setLayout(button_layout)
        to_rings_button.clicked.connect(self.ToRingsCmd)
        Extend_to_Ring_button.clicked.connect(self.Extend_to_RingCmd)
        Extend_to_Loops_button.clicked.connect(self.Extend_to_LoopCmd)
        interval_section.addWidget(slider_widget); interval_section.addWidget(button_widget)
        self.layout().addWidget(interval_section)

        # RizomUV Section
        Bridge_section = CollapsibleSection("RizomUV Bridge")
        Bridge_Dir_widget = QWidget()
        Bridge_Dir_layout = QHBoxLayout()
        Bridge_Dir_button = QPushButton('更新路径')
        self.Bridge_Dir_line_edit = QLineEdit()
        if cmds.optionVar(exists="RizomUVPath"):
            self.Bridge_Dir_line_edit.setText(cmds.optionVar(q="RizomUVPath"))
        else:
            self.Bridge_Dir_line_edit.setText(r'C:\Program Files\Rizom Lab\RizomUV 2023.0\rizomuv.exe')
        Bridge_Dir_layout.addWidget(Bridge_Dir_button); Bridge_Dir_layout.addWidget(self.Bridge_Dir_line_edit)
        Bridge_Dir_widget.setLayout(Bridge_Dir_layout)
        Bridge_section.addWidget(Bridge_Dir_widget)
        Bridge_Dir_button.clicked.connect(self.update_path)
        button_row_widget = QWidget()
        button_row_layout = QHBoxLayout()
        export_button = QPushButton('导出'); import_button = QPushButton('导入'); launch_button = QPushButton('启动RizomUV')
        button_row_layout.addWidget(export_button); button_row_layout.addWidget(import_button); button_row_layout.addWidget(launch_button)
        button_row_widget.setLayout(button_row_layout)
        Bridge_section.addWidget(button_row_widget)
        export_button.clicked.connect(self.export_obj); import_button.clicked.connect(self.import_obj); launch_button.clicked.connect(self.launch_rizom)
        self.layout().addWidget(Bridge_section)

        # Average Edge Section
        average_section = CollapsibleSection("边长优化")
        average_widget = QWidget()
        average_layout = QHBoxLayout()
        average_widget.setLayout(average_layout)
        self.average_edge_btn = QPushButton('平均边长')
        self.average_edge_btn.setMinimumHeight(30)
        self.average_edge_btn.clicked.connect(lambda: self.even_edge_loop_doit_run("even"))
        average_layout.addWidget(self.average_edge_btn)
        average_section.addWidget(average_widget)
        self.layout().addWidget(average_section)
        
        # --- Cleanup Section (清理工具) ---
        cleanup_section = CollapsibleSection("清理工具")
        cleanup_widget = QWidget()
        
        # 因为只有一行两个按钮，使用 QHBoxLayout 即可并排，也可以使用 QGridLayout
        cleanup_layout = QHBoxLayout()
        cleanup_layout.setSpacing(4)

        # 1. 先创建按钮
        btn_remove_duplicate = QPushButton('模型去重')
        btn_fix_zeroface = QPushButton('零面清理')
        
        # 统一设置按钮高度，保持与上方UI风格一致
        for btn in [btn_remove_duplicate, btn_fix_zeroface]:
            btn.setMinimumHeight(28)

        # 将按钮添加到同一行
        cleanup_layout.addWidget(btn_remove_duplicate)
        cleanup_layout.addWidget(btn_fix_zeroface)

        cleanup_widget.setLayout(cleanup_layout)
        cleanup_section.addWidget(cleanup_widget)
        self.layout().addWidget(cleanup_section)

        # 2. 再连接到自定义函数 (移到了这里)
        btn_remove_duplicate.clicked.connect(self.RemoveDuplicateMeshesCmd)
        btn_fix_zeroface.clicked.connect(self.FixZeroFacesCmd)


        cleanup_widget.setLayout(cleanup_layout)
        cleanup_section.addWidget(cleanup_widget)
        self.layout().addWidget(cleanup_section)

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout().addItem(spacer)

        bottom_btn_layout = QHBoxLayout()
        self.update_button = QPushButton('自动更新')
        self.save_settings_button = QPushButton('保存窗口设置')
        bottom_btn_layout.addWidget(self.update_button); bottom_btn_layout.addWidget(self.save_settings_button)
        self.layout().addLayout(bottom_btn_layout)
        self.update_button.clicked.connect(self.updateBonMeshTool)
        self.save_settings_button.clicked.connect(self.save_window_settings)

    # --- Commands ---
    def RenameUVSetCmd(self, *args):
        selected_objects = cmds.ls(sl=True, type='mesh') or cmds.ls(type='mesh')
        desired_name = self.rename_line_edit.text()
        for s_object in selected_objects:
            uv_ids = cmds.polyUVSet(s_object, query=True, allUVSetsIndices=True)
            if uv_ids:
                for i in uv_ids:
                    if i != 0:
                        cuvname = cmds.getAttr("{0}.uvSet[{1}].uvSetName".format(s_object, i))
                        cmds.polyUVSet(s_object, delete=True, uvSet=cuvname)
        if selected_objects:
            for each_element in selected_objects:
                cuvname = cmds.getAttr("{0}.uvSet[0].uvSetName".format(each_element))
                if cuvname != desired_name:
                    cmds.polyUVSet(each_element, rename=True, newUVSet=desired_name, uvSet=cuvname)
        cmds.inViewMessage(amg='重命名UV集为：{0}'.format(desired_name), pos='midCenter', fade=True)

    def DisplayTriangle(self, *args):
        isChecked = self.display_triangle_checkbox.isChecked()
        cmds.polyOptions(displayTriangle=isChecked)

    def UnlockNormalCmd(self, *args):
        cmds.polyNormalPerVertex(unFreezeNormal=True)

    def SoftenEdgeCmd(self, *args):
        cmds.polySoftEdge(angle=180, constructionHistory=1)

    def HardenEdgeCmd(self, *args):
        cmds.polySoftEdge(angle=0, constructionHistory=1)

    def mayaTriangleCmd(self, *args):
        selectedObjects = cmds.ls(selection=True, dag=True, type="mesh")
        for obj in selectedObjects:
            mel.eval('setAttr (\"{}\" + \".quadSplit\") 2;'.format(obj))
        self.UnlockNormalCmd()
        self.SoftenEdgeCmd()

    def unityTriangleCmd(self, *args):
        selectedObjects = cmds.ls(selection=True, dag=True, type="mesh")
        for obj in selectedObjects:
            mel.eval('setAttr (\"{}\" + \".quadSplit\") 1;'.format(obj))
        self.UnlockNormalCmd()
        self.SoftenEdgeCmd()

    def get_store_clean_selection(self):
        selection = cmds.ls(sl=True, l=True)
        if not selection: return None
        cmds.SelectEdgeMask()
        cmds.selectType(edge=True)
        cmds.select(deselect=True)
        cmds.select(selection)
        return selection

    def SelUVBrodenEdgeCmd(self, *args):
        selection = self.get_store_clean_selection()
        if not selection: return
        mesh_edges = []
        uv_border_edges = []
        for s in selection:
            try:
                edges = cmds.polyListComponentConversion(s, te=True)
                edges = cmds.ls(edges, fl=True, l=True)
                mesh_edges.extend(edges)
            except: pass
        if mesh_edges:
            for e in mesh_edges:
                edge_uvs = cmds.ls(cmds.polyListComponentConversion(e, tuv=True), fl=True)
                edge_faces = cmds.ls(cmds.polyListComponentConversion(e, tf=True), fl=True)
                if len(edge_uvs) > 2 or len(edge_faces) < 2:
                    uv_border_edges.append(e)
        if uv_border_edges: cmds.select(uv_border_edges)

    def SelHardenEdgeCmd (self, *args):
        self.get_store_clean_selection()
        cmds.polySelectConstraint(m=3, t=0x8000, sm=1)
        cmds.polySelectConstraint(m=0)

    def store_edges(self, *args):        
        global stored_edges
        selected_edges = cmds.ls(selection=True, flatten=True)
        if not selected_edges:
            cmds.warning("请选择一些边来存储。")
            return
        stored_edges = selected_edges
        print("存储了 {0} 条边。".format(len(stored_edges)))

    def select_edges(self, *args):
        self.get_store_clean_selection()
        global stored_edges
        if not ( 'stored_edges' in globals() and stored_edges ):
            cmds.warning("没有存储的边信息。")
            return
        try:
            cmds.select(stored_edges, replace=True)
        except RuntimeError as e:
            cmds.warning("选择存储的边时出错: {0}".format(e))

    def TranPositoUVCmd (self, *args):
        cmds.transferAttributes(transferUVs=1,sampleSpace=1,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def TranUVtoPosiCmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=3,searchMethod=3,)
        cmds.delete(constructionHistory=True)
        
    def TranPositoBordenECmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=0,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    # --- Expression Mirror (Converted from MEL) ---
    def ExpressionMirrorCmd(self, *args):
        """整合的表情镜像逻辑：选择两个物体，第一个是目标表情，第二个是基础模型"""
        selection = cmds.ls(sl=True)
        if len(selection) < 2:
            cmds.warning("请先选择【目标表情物体】，然后加选【基础模型】。")
            return
        
        target = selection[0]
        base = selection[1]
        
        # 1. 复制模型
        copy_base = cmds.duplicate(base, n="copybaseFANTAKEY")[0]
        copy_base_mirror = cmds.duplicate(base, n="copybaseFANTAKEY1")[0]
        copy_target = cmds.duplicate(target, n="copytargetFANTAKEY")[0]
        
        # 2. 创建混合变形 (BlendShape)
        bs_node = cmds.blendShape(copy_target, copy_base, n="emotional_expressionFANTAKEY")[0]
        
        # 3. 镜像缩放
        cmds.setAttr("{}.scaleX".format(copy_base), -1)
        
        # 4. 创建包裹变形 (Wrap)
        cmds.select([copy_base_mirror, copy_base], r=True)
        # 使用 MEL 执行 CreateWrap 保持行为一致
        mel.eval("CreateWrap")
        
        # 5. 激活表情并提取结果
        cmds.setAttr("{}.{}".format(bs_node, copy_target), 1)
        done_obj = cmds.duplicate(copy_base_mirror, n="doneFANTAKEY")[0]
        
        # 6. 清理临时物体
        temp_objs = [copy_base, copy_base_mirror, copy_target]
        # Wrap 产生的 Base 节点通常带有 Base 后缀
        wrap_base = copy_base_mirror + "Base"
        if cmds.objExists(wrap_base): temp_objs.append(wrap_base)
        
        cmds.delete(temp_objs)
        cmds.select(done_obj, r=True)
        cmds.inViewMessage(amg='表情镜像完成！生成结果：doneFANTAKEY', pos='midCenter', fade=True)

    # --- Interval Selection & Others (Same as original) ---
    def Ring_slider_value_changed(self, value):
        self.Ring_value_label.setText("Ring间隔数: {0}".format(value))
        self.preview_selection()

    def loop_slider_value_changed(self, value):
        self.loop_value_label.setText("loop间隔数: {0}".format(value))
        self.preview_selection()

    def get_current_Ring_slider_value(self):
        return self.slider.value()
        
    def get_current_loop_slider_value(self):
        return self.loop_slider.value()

    def get_selected_edge_count(self):
        selection = cmds.ls(selection=True, flatten=True)
        raw = len([item for item in selection if '.e[' in item])
        try:
            if is_symmetry_on():
                return raw // 2
        except: pass
        return raw

    def store_selected_edges(self):
        self.selected_edges = cmds.ls(selection=True, flatten=True)

    def ToRingsCmd(self):
        self.store_selected_edges()
        self.preview_selection()
        
    def Extend_to_RingCmd(self):
        mel.eval('polySelectEdgesEveryN("edgeRing", 1)')
        
    def Extend_to_LoopCmd(self):
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')

    def preview_selection(self):
        if not hasattr(self, 'selected_edges') or not self.selected_edges: return
        cmds.select(clear=True)
        cmds.select(self.selected_edges)
        edge_count = self.get_selected_edge_count()
        current_Ring_value = self.get_current_Ring_slider_value()
        current_Loop_value = self.get_current_loop_slider_value()
        if current_Ring_value != 0:
            n = edge_count + current_Ring_value
            mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        if current_Loop_value != 0:
            x = edge_count + current_Loop_value
            mel.eval('polySelectEdgesEveryN("edgeLoop", {0})'.format(x))

    def update_path(self):
        new_path = self.Bridge_Dir_line_edit.text()
        cmds.optionVar(sv=("RizomUVPath", new_path))
        self.write_loader()
        
    def setup_dirs(self):
        self.ObjectType = 'fbx'
        self.MayaScriptDir = cmds.internalVar(userScriptDir=True)
        self.BridgeDir = os.path.join(self.MayaScriptDir, 'BonMeshTool/')
        self.ObjectDir = os.path.join(self.BridgeDir, 'data/RBMObject.' + self.ObjectType).replace("\\", "/")
        self.LoaderDir = os.path.join(self.BridgeDir, 'data/Loader.lua').replace("\\", "/")

    def write_loader(self):
        self.RizomUVDir = self.Bridge_Dir_line_edit.text()
        ZomLuaScript = 'ZomLoad({File={Path="' + self.ObjectDir + '", ImportGroups=true, XYZUVW=true, UVWProps=true}})'
        if 'rizomuv.exe' in self.RizomUVDir.lower():
            if not os.path.exists(os.path.dirname(self.LoaderDir)): os.makedirs(os.path.dirname(self.LoaderDir))
            with open(self.LoaderDir, 'wt') as f:
                f.write(ZomLuaScript)
            cmds.inViewMessage(amg='RizomUV写入成功!', pos='midCenter', fade=True)

    def export_obj(self):
        self.write_loader()
        if 'fbx' in self.ObjectType:
            cmds.file(self.ObjectDir, force=1, type='FBX export', op='groups=1', pr=1, es=1)
        elif 'obj' in self.ObjectType:
            cmds.file(self.ObjectDir, force=1, type="OBJexport", options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1", es=1)

    def launch_rizom(self):
        subprocess.Popen('"' + self.RizomUVDir + '"' + ' -cfi ' + self.LoaderDir)

    def import_obj(self):
        SelOBJ = cmds.ls(sl=True)
        if SelOBJ: cmds.delete(SelOBJ)
        if 'fbx' in self.ObjectType:
            cmds.file(self.ObjectDir, i=1, ignoreVersion=1, mergeNamespacesOnClash=0, rpr='RBMObject', type='FBX', pr=1)
        elif 'obj' in self.ObjectType:
            cmds.file(self.ObjectDir, i=1, gn='RizomUVBridge', type="OBJ", gr=1)

    def even_edge_loop_doit_run(self, smooth_type):
        sel = cmds.ls(selection=True, fl=1)
        if not sel: return
        shape = cmds.listRelatives(sel, parent=True)
        edge_loop_groups = self.get_edge_ring_group(0, '')
        for group in edge_loop_groups:
            cmds.select(group)
            self.even_edge_loop_doit(smooth_type)
        cmds.select(sel)

    def even_edge_loop_doit(self, smooth_type):
        temp_curve = 'tempEvenCurve'
        if cmds.objExists(temp_curve): cmds.delete(temp_curve)
        sel = cmds.ls(selection=True, fl=1)
        if not sel: return
        circle_state, vertex_list = self.vtx_loop_order_check()
        cmds.polyToCurve(form=2, degree=1, conformToSmoothMeshPreview=1)
        cmds.rename(temp_curve)
        curve_cvs = cmds.ls(temp_curve + '.cv[*]', fl=1)
        if len(curve_cvs) > 2:
            cmds.rebuildCurve(temp_curve, ch=1, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=0, d=1, tol=0)
        for i in range(len(curve_cvs)):
            pos = cmds.xform(curve_cvs[i], a=1, ws=1, q=1, t=1)
            if i < len(vertex_list):
                cmds.xform(vertex_list[i], a=1, ws=1, t=(pos[0], pos[1], pos[2]))
        cmds.delete(temp_curve)

    def get_edge_ring_group(self, list_sort, list_input):
        sel_edges = cmds.ls(selection=True, fl=1)
        if not sel_edges: return []
        trans = sel_edges[0].split(".")[0]
        e2v_dict = {}
        e2v_infos = cmds.polyInfo(sel_edges, ev=True)
        for info in e2v_infos:
            ev_list = [int(i) for i in re.findall('\\d+', info)]
            e2v_dict[ev_list[0]] = ev_list[1:]
        edge_groups = []
        while e2v_dict:
            start_edge, start_vtxs = e2v_dict.popitem()
            edges_grp = [start_edge]
            num = 0
            for vtx in start_vtxs:
                current_vtx = vtx
                while True:
                    next_edges = [k for k in e2v_dict if current_vtx in e2v_dict[k]]
                    if next_edges and len(next_edges) == 1:
                        next_edge = next_edges[0]
                        if num == 0: edges_grp.append(next_edge)
                        else: edges_grp.insert(0, next_edge)
                        next_vtxs = e2v_dict[next_edge]
                        current_vtx = [v for v in next_vtxs if v != current_vtx][0]
                        e2v_dict.pop(next_edge)
                    else: break
                num += 1
            edge_groups.append(edges_grp)
        return [[trans + '.e[' + str(edge) + ']' for edge in group] for group in edge_groups]

    def vtx_loop_order_check(self):
        sel_edges = cmds.ls(selection=True, fl=1)
        if not sel_edges: return 0, []
        transform_node = cmds.ls(sel_edges[0], o=True, l=True)
        edge_number_list = [re.findall(r'\d+', e.split('.')[-1])[0] for e in sel_edges]
        vertex_numbers = []
        for edge in sel_edges:
            ev_list = cmds.polyInfo(edge, ev=True)
            vertex_numbers.extend(re.findall(r'\d+', ev_list[0].split(':')[-1]))
        duplicates = set([x for x in vertex_numbers if vertex_numbers.count(x) > 1])
        endpoints = list(set(vertex_numbers) - duplicates)
        circle_state = 0
        if not endpoints:
            circle_state = 1
            endpoints.append(vertex_numbers[0])
        vertex_order = [endpoints[0]]
        count = 0
        while duplicates and count < 1000:
            current_vtx = "{0}.vtx[{1}]".format(transform_node[0], vertex_order[-1])
            ve_list = cmds.polyInfo(current_vtx, ve=True)
            edge_nums = re.findall(r'\d+', ve_list[0].split(':')[-1])
            found_edges = [g for g in edge_nums if g in edge_number_list]
            if not found_edges: break
            next_edge = found_edges[0]
            edge_number_list.remove(next_edge)
            edge_vtxs = cmds.polyInfo("{0}.e[{1}]".format(transform_node[0], next_edge), ev=True)
            vtx_nums = re.findall(r'\d+', edge_vtxs[0].split(':')[-1])
            found_vtxs = [g for g in vtx_nums if g in duplicates]
            if not found_vtxs: break
            next_vtx = found_vtxs[0]
            duplicates.remove(next_vtx)
            vertex_order.append(next_vtx)
            count += 1
        if circle_state == 0 and len(endpoints) > 1: vertex_order.append(endpoints[1])
        final_vertices = ["{0}.vtx[{1}]".format(transform_node[0], v) for v in vertex_order]
        return circle_state, final_vertices

    # --- 清理场景Cleanup Commands ---
    def RemoveDuplicateMeshesCmd(self, *args):
        # 容差值（保留的小数位数），用于处理Maya内部坐标的浮点精度误差
        tolerance = 4 
        
        # 1. 获取当前选中的所有对象 (使用 long=True 获取全路径)
        selection = cmds.ls(selection=True, long=True)
        if not selection:
            cmds.warning(u"请先在场景中选中需要检查的模型！")
            return

        # 2. 过滤选择，只保留多边形模型(过滤掉灯光、摄像机或空组)
        transforms = []
        for obj in selection:
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
            if shapes:
                # 检查是否有显示的 mesh 形节点
                for shape in shapes:
                    if cmds.nodeType(shape) == 'mesh' and not cmds.getAttr(shape + ".intermediateObject"):
                        transforms.append(obj)
                        break # 只要有一个mesh shape就加入列表并跳出循环

        if not transforms:
            cmds.warning(u"选中的对象中没有找到多边形模型。")
            return

        # 去重（防止误选导致重复）
        transforms = list(set(transforms))
        
        mesh_dict = {}
        duplicates_to_select = []

        for obj in transforms:
            # 3. 获取顶点数量
            vtx_count = cmds.polyEvaluate(obj, vertex=True)
            
            # 4. 获取世界坐标下的精确包围盒 (xmin, ymin, zmin, xmax, ymax, zmax)
            bbox = cmds.exactWorldBoundingBox(obj)
            
            # 计算包围盒中心点，并保留指定小数位
            cx = round((bbox[0] + bbox[3]) / 2.0, tolerance)
            cy = round((bbox[1] + bbox[4]) / 2.0, tolerance)
            cz = round((bbox[2] + bbox[5]) / 2.0, tolerance)
            
            # 5. 生成特征签名 (顶点数, X, Y, Z)
            signature = (vtx_count, cx, cy, cz)
            
            # 6. 存入字典进行比对
            if signature in mesh_dict:
                mesh_dict[signature].append(obj)
            else:
                mesh_dict[signature] = [obj]

        # 收集重叠的模型
        for sig, objs in mesh_dict.items():
            if len(objs) > 1:
                # 保留第一个模型作为原模型，把其余的视为多余的复制品
                duplicates_to_select.extend(objs[1:])

        # 结果处理
        if duplicates_to_select:
            cmds.select(duplicates_to_select, replace=True)
            message = u"发现 {0} 个重叠的误复制模型！已经为您选中它们，可以直接按Delete删除。".format(len(duplicates_to_select))
            cmds.warning(message)
            print(message)
        else:
            # 恢复最初的整体选择
            cmds.select(selection, replace=True)
            message = u"检查完毕，选中的模型中没有发现重叠的复制品。"
            print(message)
            cmds.inViewMessage(amg=message, pos='midCenter', fade=True, fst=2000)


    def FixZeroFacesCmd(self, *args):
        # 获取当前选中的模型
        selection = cmds.ls(selection=True, objectsOnly=True)
        
        if not selection:
            cmds.warning(u"请先选择需要清理的模型！")
            return

        for obj in selection:
            # 1. 查找并删除完全重合的面 (Lamina Faces)
            cmds.select(obj)
            lamina_faces = cmds.polyInfo(laminaFaces=True)
            if lamina_faces:
                cmds.delete(lamina_faces)
                print(u"成功删除 {0} 上的重合面: {1} 个".format(obj, len(lamina_faces)))
            else:
                print(u"{0} 没有发现完全重合的面。".format(obj))

            # 2. 合并极近的顶点（清除0厚度挤出产生的重合点）
            cmds.select(obj)
            # 阈值设置为0.0001，防止误伤正常细节
            cmds.polyMergeVertex(distance=0.0001, alwaysMergeTwoVertices=False)
            print(u"{0} 的重合顶点已合并。".format(obj))

        # 恢复最初的选择
        cmds.select(selection)
        cmds.confirmDialog(title=u'清理完成', message=u'重合面和重合顶点清理完毕！', button=['OK'])


    def updateBonMeshTool(self):
        script_directory = cmds.internalVar(userScriptDir=True)
        full_path = os.path.join(script_directory, 'BonMeshTool')
        message = ""
        if not os.path.exists(full_path):
            message = 'BonMeshTool 文件夹不存在'
        else:
            try:
                result = subprocess.run(['git', '-C', full_path, 'pull'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                message = '已经是最新的版本' if "Already up to date." in result.stdout else '更新成功'
            except: message = '更新失败'
        QTimer.singleShot(100, lambda: cmds.inViewMessage(amg=message, pos='midCenter', fade=True))
        
    def restore_window_settings(self):
        if cmds.optionVar(exists='BonMeshToolUI_width'):
            self.resize(cmds.optionVar(q='BonMeshToolUI_width'), cmds.optionVar(q='BonMeshToolUI_height'))
        if cmds.optionVar(exists='BonMeshToolUI_position'):
            pos = cmds.optionVar(q='BonMeshToolUI_position').split(',')
            self.move(int(pos[0]), int(pos[1]))

    def save_window_settings(self):
        cmds.optionVar(intValue=('BonMeshToolUI_width', self.width()))
        cmds.optionVar(intValue=('BonMeshToolUI_height', self.height()))
        cmds.optionVar(stringValue=('BonMeshToolUI_position', '{},{}'.format(self.pos().x(), self.pos().y())))
        cmds.inViewMessage(amg='<font color="#FFFF00">保存成功！</font>', pos='midCenter', fade=True)

def show_bon_mesh_tool_ui():
    global bon_mesh_tool_ui
    try: bon_mesh_tool_ui.close(); bon_mesh_tool_ui.deleteLater()
    except: pass
    bon_mesh_tool_ui = BonMeshToolUI()
    bon_mesh_tool_ui.show(dockable=True, area='right', width=330, height=450)

if __name__ == '__main__':
    show_bon_mesh_tool_ui()
# 在脚本最后面添加
def main():
    show_bon_mesh_tool_ui()

if __name__ == '__main__':
    main()
