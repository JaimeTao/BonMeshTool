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
##--------------------------------------------------------------------------
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2.QtWidgets import *
from PySide2.QtCore import *
import maya.cmds as cmds
import maya.mel as mel
import subprocess
import os
import re

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
        self.setMinimumHeight(400)

        # Restore window settings if they exist
        self.restore_window_settings()

        # Section for UV renaming
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

        # Section for triangle operation
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
        maya_button.setMinimumHeight(maya_button.sizeHint().height() * 2)
        unity_button.setMinimumHeight(unity_button.sizeHint().height() * 2)
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

        # Section for quick selection tools
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

        # Section for transferring attributes
        transfer_section = CollapsibleSection("传递属性工具")
        transfer_widget = QWidget()
        transfer_layout = QHBoxLayout()
        transfer_pos_to_uv_button = QPushButton('位置toUV')
        transfer_uv_to_pos_button = QPushButton('UVto位置')
        transfer_pos_to_border_button = QPushButton('边界to边界')
        transfer_pos_to_uv_button.clicked.connect(self.TranPositoUVCmd)
        transfer_uv_to_pos_button.clicked.connect(self.TranUVtoPosiCmd)
        transfer_pos_to_border_button.clicked.connect(self.TranPositoBordenECmd)
        transfer_layout.addWidget(transfer_pos_to_uv_button)
        transfer_layout.addWidget(transfer_uv_to_pos_button)
        transfer_layout.addWidget(transfer_pos_to_border_button)
        transfer_widget.setLayout(transfer_layout)
        transfer_section.addWidget(transfer_widget)
        self.layout().addWidget(transfer_section)

        # Section for interval selection tools
        interval_section = CollapsibleSection("间隔选择工具")
        slider_widget = QWidget()
        slider_layout = QVBoxLayout()

        interval_slider_layout = QHBoxLayout()
        self.Ring_value_label = QLabel("Ring间隔数: %d" % 1)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(20)
        self.slider.setValue(1)
        interval_slider_layout.addWidget(self.Ring_value_label)
        interval_slider_layout.addWidget(self.slider)
        self.slider.valueChanged.connect(self.Ring_slider_value_changed)
        slider_layout.addLayout(interval_slider_layout)

        loop_slider_layout = QHBoxLayout()
        self.loop_value_label = QLabel("loop间隔数: %d" % 0)
        self.loop_slider = QSlider(Qt.Horizontal)
        self.loop_slider.setMinimum(0)
        self.loop_slider.setMaximum(20)
        self.loop_slider.setValue(0)
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
        button_layout.addWidget(to_rings_button)
        button_layout.addWidget(Extend_to_Ring_button)
        button_layout.addWidget(Extend_to_Loops_button)
        button_widget.setLayout(button_layout)
        to_rings_button.clicked.connect(self.ToRingsCmd)
        Extend_to_Ring_button.clicked.connect(self.Extend_to_RingCmd)
        Extend_to_Loops_button.clicked.connect(self.Extend_to_LoopCmd)
        
        interval_section.addWidget(slider_widget)
        interval_section.addWidget(button_widget)
        self.layout().addWidget(interval_section)

        # Section for RizomUV Bridge
        Bridge_section = CollapsibleSection("RizomUV Bridge")
        Bridge_Dir_widget = QWidget()
        Bridge_Dir_layout = QHBoxLayout()
        Bridge_Dir_button = QPushButton('更新路径')
        self.Bridge_Dir_line_edit = QLineEdit()
        if cmds.optionVar(exists="RizomUVPath"):
            self.Bridge_Dir_line_edit.setText(cmds.optionVar(q="RizomUVPath"))
        else:
            self.Bridge_Dir_line_edit.setText(r'C:\Program Files\Rizom Lab\RizomUV 2023.0\rizomuv.exe')
        Bridge_Dir_layout.addWidget(Bridge_Dir_button)
        Bridge_Dir_layout.addWidget(self.Bridge_Dir_line_edit)
        Bridge_Dir_widget.setLayout(Bridge_Dir_layout)
        Bridge_section.addWidget(Bridge_Dir_widget)
        self.layout().addWidget(Bridge_section)
        Bridge_Dir_button.clicked.connect(self.update_path)

        button_row_widget = QWidget()
        button_row_layout = QHBoxLayout()
        export_button = QPushButton('导出')
        import_button = QPushButton('导入')
        launch_button = QPushButton('启动RizomUV')
        button_row_layout.addWidget(export_button)
        button_row_layout.addWidget(import_button)
        button_row_layout.addWidget(launch_button)
        button_row_widget.setLayout(button_row_layout)
        Bridge_section.addWidget(button_row_widget)
        export_button.clicked.connect(self.export_obj)
        import_button.clicked.connect(self.import_obj)
        launch_button.clicked.connect(self.launch_rizom)
        self.layout().addWidget(Bridge_section)
###### 平均化边长UI######
        # 平均化边长度模块 - 独立布局+正确事件绑定
        average_section = CollapsibleSection("边长优化")
        # 创建独立的布局容器（避免复用其他模块的transfer_layout导致错乱）
        average_widget = QWidget()
        average_layout = QHBoxLayout()  # 独立水平布局
        average_widget.setLayout(average_layout)  # 给容器设置布局
        
        # 1. 创建平均边长按钮
        self.average_edge_btn = QPushButton('平均边长')
        # 设置按钮样式（与其他功能按钮视觉统一）
        self.average_edge_btn.setMinimumHeight(30)  # 增加按钮高度，提升点击体验
        # 2. 绑定按钮事件：直接触发平均化命令（固定传递"Average"模式参数）
        self.average_edge_btn.clicked.connect(
            lambda: self.even_edge_loop_doit_run("even")  # 传递smooth_type为"even"（对应Average模式）
        )
        
        # 3. 将按钮添加到独立布局中
        average_layout.addWidget(self.average_edge_btn)
        # 4. 将布局容器添加到折叠面板
        average_section.addWidget(average_widget)
        # 5. 将整个平均化模块添加到主界面
        self.layout().addWidget(average_section)
### 平均化线段长度模块结束 ###
        # 添加一个扩展项来推动按钮到底部
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout().addItem(spacer)

        # 按钮布局
        button_layout = QHBoxLayout()
        self.update_button = QPushButton('自动更新')
        self.save_settings_button = QPushButton('保存窗口设置')
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.save_settings_button)
        self.layout().addLayout(button_layout)

        # 按钮连接功能
        self.update_button.clicked.connect(self.updateBonMeshTool)
        self.save_settings_button.clicked.connect(self.save_window_settings)

    def RenameUVSetCmd(self, *args):
        selected_objects = cmds.ls(type='mesh')
        desired_name = self.rename_line_edit.text()  # 获取文本输入框的内容
        for s_object in selected_objects:
            uv_ids = cmds.polyUVSet(s_object, query=True, allUVSetsIndices=True)
            for i in uv_ids:
                if i != 0:
                    cuvname = cmds.getAttr(f"{s_object}.uvSet[{i}].uvSetName")
                    cmds.polyUVSet(s_object, delete=True, uvSet=cuvname)
        for each_element in selected_objects:
            cuvname = cmds.getAttr(f"{each_element}.uvSet[0].uvSetName")
            if cuvname != desired_name:
                cmds.polyUVSet(each_element, rename=True, newUVSet=desired_name, uvSet=cuvname)
        #cmds.warning("重命名UV集为：", desired_name)
        cmds.inViewMessage(amg=f'重命名UV集为：{desired_name}', pos='midCenter', fade=True)

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
            mel.eval('setAttr (\"{}\" + \".quadSplit\") 2;'.format(obj, ""))
        self.UnlockNormalCmd()
        self.SoftenEdgeCmd()

    def unityTriangleCmd(self, *args):
        selectedObjects = cmds.ls(selection=True, dag=True, type="mesh")
        for obj in selectedObjects:
            mel.eval('setAttr (\"{}\" + \".quadSplit\") 1;'.format(obj, ""))
        self.UnlockNormalCmd()
        self.SoftenEdgeCmd()

    def get_store_clean_selection(self):
        """获取当前选择的对象并存储，启用边选择模式，清空当前选择，然后重新选择对象。"""
        # 获取当前选择的对象并存储
        selection = cmds.ls(sl=True, l=True)
        if not selection:
            return None

        # 启用边选择掩码并清空当前选择
        cmds.SelectEdgeMask()          # 启用边选择掩码
        cmds.selectType(edge=True)     # 设置选择类型为边
        cmds.select(deselect=True)     # 清空当前选择

        # 重新选择之前存储的对象
        cmds.select(selection)

        return selection

    def SelUVBrodenEdgeCmd(self, *args):
        # 获取当前选择的对象并清空当前选择存储
        selection = self.get_store_clean_selection()
        # 执行选择 UV 边界的逻辑
        mesh_edges = []
        uv_border_edges = []

        for s in selection:
            try:
                edges = cmds.polyListComponentConversion(s, te=True)
                edges = cmds.ls(edges, fl=True, l=True)
                mesh_edges.extend(edges)
            except:
                pass

        if mesh_edges:
            for e in mesh_edges:
                edge_uvs = cmds.ls(cmds.polyListComponentConversion(e, tuv=True), fl=True)
                edge_faces = cmds.ls(cmds.polyListComponentConversion(e, tf=True), fl=True)
                
                # 判断是否为UV边界边或孤立边
                if len(edge_uvs) > 2:
                    uv_border_edges.append(e)
                elif len(edge_faces) < 2:
                    uv_border_edges.append(e)

        # 如果找到 UV 边界边，选择这些边
        if uv_border_edges:
            cmds.select(uv_border_edges)

    def SelHardenEdgeCmd (self, *args):
        # 获取当前选择的对象并清空当前选择存储
        selection = self.get_store_clean_selection()

        # 设置边选择约束
        cmds.polySelectConstraint(m=3, t=0x8000, sm=1)
        cmds.polySelectConstraint(m=0)

    ##
    def store_edges(self, *args):        
        global stored_edges
        selected_edges = cmds.ls(selection=True, flatten=True)

        if not selected_edges:
            cmds.warning("请选择一些边来存储。")
            return

        stored_edges = selected_edges
        print(f"存储了 {len(stored_edges)} 条边。")

    def select_edges(self, *args):


        # 获取当前选择的对象并清空当前选择存储
        selection = self.get_store_clean_selection()

        global stored_edges

        if not stored_edges:
            cmds.warning("没有存储的边信息。")
            return

        try:
            cmds.select(stored_edges, replace=True)
            print(f"选择了 {len(stored_edges)} 条边。")
        except RuntimeError as e:
            cmds.warning(f"选择存储的边时出错: {e}")

    def TranPositoUVCmd (self, *args):
        cmds.transferAttributes(transferUVs=1,sampleSpace=1,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def TranUVtoPosiCmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=3,searchMethod=3,)
        cmds.delete(constructionHistory=True)
        
    def TranPositoBordenECmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=0,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def Ring_slider_value_changed(self, value):
        self.Ring_value_label.setText("Ring间隔数: %d" % value)
        self.preview_selection()

    def loop_slider_value_changed(self, value):
        self.loop_value_label.setText("loop间隔数: %d" % value)
        self.preview_selection()

    def get_current_Ring_slider_value(self):
        current_value = self.slider.value()
        print("Current slider value:", current_value)
        return current_value
        
    def get_current_loop_slider_value(self):
        current_value = self.loop_slider.value()
        print("Current loop slider value:", current_value)
        return current_value

    def get_selected_edge_count(self):
        selection = cmds.ls(selection=True, flatten=True)
        edge_count = 0
        for item in selection:
            if '.e[' in item:
                edge_count += 1
        print("Selected edge count:", edge_count)
        return edge_count

    def store_selected_edges(self):
        self.selected_edges = cmds.ls(selection=True, flatten=True)
        print("Stored selected edges:", self.selected_edges)

    def ToRingsCmd(self):
        self.store_selected_edges()
        self.preview_selection()
        
    def Extend_to_RingCmd(self):
        mel.eval('polySelectEdgesEveryN("edgeRing", 1)')
        
    def Extend_to_LoopCmd(self):
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')

    def preview_selection(self):
        if not self.selected_edges:
            return

        cmds.select(clear=True)
        cmds.select(self.selected_edges)

        edge_count = self.get_selected_edge_count()
        current_Ring_value = self.get_current_Ring_slider_value()
        current_Loop_value = self.get_current_loop_slider_value()

        # Condition for edgeRing selection
        if current_Ring_value != 0:
            n = edge_count + current_Ring_value
            print("Computed Ring value (n):", n)
            mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))

        # Condition for edgeLoop selection
        x = edge_count + current_Loop_value
        if current_Loop_value != 0:
            x = edge_count + current_Loop_value
        else:
            x = -1
        print("Computed Loop value (x):", x)
        mel.eval('polySelectEdgesEveryN("edgeLoop", {0})'.format(x))
        
    def update_path(self):
        new_path = self.Bridge_Dir_line_edit.text()
        cmds.optionVar(sv=("RizomUVPath", new_path))
        self.write_loader()
        
    def setup_dirs(self):
        self.ObjectType = 'fbx'
        self.MayaScriptDir = cmds.internalVar(userScriptDir=True)
        self.BridgeDir = self.MayaScriptDir + 'BonMeshTool/'
        self.ObjectDir = self.BridgeDir + 'data/RBMObject.' + self.ObjectType
        self.LoaderDir = self.BridgeDir + 'data/Loader.lua'
        self.ConfigDir = self.BridgeDir + 'data/config.json'

    def write_loader(self):
        self.RizomUVDir = self.Bridge_Dir_line_edit.text()
        ZomLuaScript = ('ZomLoad({File={Path="' + self.ObjectDir + '", ImportGroups=true, XYZUVW=true, UVWProps=true}})')
        U3dLuaScript = ('U3dLoad({File={Path="' + self.ObjectDir + '", ImportGroups=true, XYZUVW=true, UVWProps=true}})')
        if 'rizomuv.exe' in self.RizomUVDir:
            with open(self.LoaderDir, 'wt') as f:
                f.write(ZomLuaScript)
                cmds.inViewMessage(amg='RizomUV写入成功!', pos='midCenter', fade=True)
        else:
            cmds.inViewMessage(amg='RizomUV写入失败!', pos='midCenter', fade=True)

    def export_obj(self):
        self.write_loader()
        SelOBJ = cmds.ls(sl=True)
        if 'fbx' in self.ObjectType:
            cmds.file(self.ObjectDir, force=1, type='FBX export', op='groups=1', pr=1, es=1)
            print('Export FBX complete!')
        elif 'obj' in self.ObjectType:
            cmds.file(self.ObjectDir, force=1, type="OBJexport", options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1", es=1)
            cmds.warning('Export OBJ complete!')
        else:
            cmds.error('Export Object Type Error!')

    def launch_rizom(self):
        subprocess.Popen('"' + self.RizomUVDir + '"' + ' -cfi ' + self.LoaderDir)

    def import_obj(self):
        SelOBJ = cmds.ls(sl=True)
        for item in SelOBJ:
            cmds.delete()
        if 'fbx' in self.ObjectType:
            cmds.file(self.ObjectDir, i=1, ignoreVersion=1, mergeNamespacesOnClash=0, rpr='RBMObject', type='FBX', pr=1)
            cmds.select(SelOBJ, r=True)
            print('Import FBX complete!')
        elif 'obj' in self.ObjectType:
            cmds.file(self.ObjectDir, i=1, gn='RizomUVBridge', type="OBJ", gr=1)
            cmds.warning('Import OBJ complete!')
        else:
            cmds.error('Import Object Type Error!')
###平均化线段长度###

    def even_edge_loop_doit_run(self, smooth_type):
        """处理选中的边环组，执行均匀化操作"""
        # 获取当前选择的边
        sel = cmds.ls(selection=True, fl=1)
        if not sel:
            cmds.warning("请先选择多边形的边")
            return

        # 保存原始形状节点
        shape = cmds.listRelatives(sel, parent=True)
        if not shape:
            cmds.warning("无法获取选择的形状节点")
            return

        # 临时调整显示平滑度
        cmds.displaySmoothness(
            divisionsU=0,
            divisionsV=0,
            pointsWire=4,
            pointsShaded=1,
            polygonObject=1
        )

        # 获取边环组并处理
        edge_loop_groups = self.get_edge_ring_group(0, '')
        for group in edge_loop_groups:
            cmds.select(group)
            self.even_edge_loop_doit(smooth_type)

        # 恢复初始选择状态
        cmds.select(sel)
        # 恢复边组件选择模式
        cmd = f'doMenuComponentSelection("{shape[0]}", "edge");'
        mel.eval(cmd)
        cmds.select(sel)

    def even_edge_loop_doit(self, smooth_type):
        """对单个边环执行均匀化处理"""
        # 清理临时曲线
        temp_curve = 'tempEvenCurve'
        if cmds.objExists(temp_curve):
            cmds.delete(temp_curve)

        # 获取当前选择的边
        sel = cmds.ls(selection=True, fl=1)
        if not sel:
            return

        # 检查边环顶点顺序
        circle_state, vertex_list = self.vtx_loop_order_check()
        
        # 将边环转换为曲线
        cmds.polyToCurve(
            form=2,
            degree=1,
            conformToSmoothMeshPreview=1
        )
        cmds.rename(temp_curve)
        curve_cvs = cmds.ls(f'{temp_curve}.cv[*]', fl=1)

        # 校正顶点顺序
        curve_pos = cmds.xform(curve_cvs[0], a=1, ws=1, q=1, t=1)
        edge_pos = cmds.xform(vertex_list[0], a=1, ws=1, q=1, t=1)
        if curve_pos != edge_pos:
            vertex_list = vertex_list[::-1]

        # 处理曲线（仅保留Average模式）
        if len(curve_cvs) > 2:
            # 重建曲线为线性
            cmds.rebuildCurve(
                temp_curve,
                ch=1,
                rpo=1,
                rt=0,
                end=1,
                kr=0,
                kcp=0,
                kep=1,
                kt=0,
                s=0,
                d=1,
                tol=0
            )
            
            # 处理少量CV点的情况
            if len(curve_cvs) < 4:
                cmds.delete(f'{temp_curve}.cv[1]', f'{temp_curve}.cv[3]')
                curve_cvs = cmds.ls(f'{temp_curve}.cv[*]', fl=1)

            # 校验顶点顺序（处理浮点精度）
            curve_pos = [round(p, 3) for p in cmds.xform(curve_cvs[0], a=1, ws=1, q=1, t=1)]
            edge_pos = [round(p, 3) for p in cmds.xform(vertex_list[0], a=1, ws=1, q=1, t=1)]

        # 应用曲线位置到顶点
        cmds.delete(temp_curve, ch=1)  # 删除历史
        for i in range(len(curve_cvs)):
            pos = cmds.xform(curve_cvs[i], a=1, ws=1, q=1, t=1)
            cmds.xform(vertex_list[i], a=1, ws=1, t=(pos[0], pos[1], pos[2]))
        
        # 清理临时曲线
        cmds.delete(temp_curve)

    def get_edge_ring_group(self, list_sort, list_input):
        """获取并分组连续的边环"""
        sel_edges = cmds.ls(selection=True, fl=1)
        if not sel_edges:
            return []

        # 提取变换节点
        trans = sel_edges[0].split(".")[0]
        
        # 构建边-顶点映射字典
        e2v_dict = {}
        e2v_infos = cmds.polyInfo(sel_edges, ev=True)
        for info in e2v_infos:
            ev_list = [int(i) for i in re.findall('\\d+', info)]
            e2v_dict[ev_list[0]] = ev_list[1:]

        edge_groups = []
        # 遍历边字典，聚合连续的边
        while e2v_dict:
            try:
                start_edge, start_vtxs = e2v_dict.popitem()
            except KeyError:
                break

            edges_grp = [start_edge]
            num = 0
            for vtx in start_vtxs:
                current_vtx = vtx
                while True:
                    # 查找关联的边
                    next_edges = [k for k in e2v_dict if current_vtx in e2v_dict[k]]
                    if next_edges and len(next_edges) == 1:
                        next_edge = next_edges[0]
                        # 按方向插入边
                        if num == 0:
                            edges_grp.append(next_edge)
                        else:
                            edges_grp.insert(0, next_edge)
                        
                        # 更新当前顶点
                        next_vtxs = e2v_dict[next_edge]
                        current_vtx = [v for v in next_vtxs if v != current_vtx][0]
                        e2v_dict.pop(next_edge)
                    else:
                        break
                num += 1
            edge_groups.append(edges_grp)

        # 格式化边路径
        return [
            [f"{trans}.e[{str(edge)}]" for edge in group]
            for group in edge_groups
        ]

    def vtx_loop_order_check(self):
        """检查并获取边环顶点的有序列表"""
        sel_edges = cmds.ls(selection=True, fl=1)
        if not sel_edges:
            return 0, []

        # 获取形状节点和变换节点
        shape_node = cmds.listRelatives(sel_edges[0], fullPath=True, parent=True)
        transform_node = cmds.listRelatives(shape_node[0], fullPath=True, parent=True)
        if not transform_node:
            return 0, []

        # 提取边ID列表
        edge_number_list = []
        for edge in sel_edges:
            parts = (edge.split('.')[1].split('\n')[0]).split(' ')
            for part in parts:
                number = ''.join([n for n in part.split('|')[-1] if n.isdigit()])
                if number:
                    edge_number_list.append(number)

        # 提取顶点ID
        vertex_numbers = []
        for edge in sel_edges:
            ev_list = cmds.polyInfo(edge, ev=True)
            parts = (ev_list[0].split(':')[1].split('\n')[0]).split(' ')
            for part in parts:
                number = ''.join([n for n in part.split('|')[-1] if n.isdigit()])
                if number:
                    vertex_numbers.append(number)

        # 确定端点和闭合状态
        duplicates = set([x for x in vertex_numbers if vertex_numbers.count(x) > 1])
        endpoints = list(set(vertex_numbers) - duplicates)
        circle_state = 0  # 0=开放, 1=闭合

        if not endpoints:  # 闭合边环
            circle_state = 1
            endpoints.append(vertex_numbers[0])

        # 构建顶点顺序
        vertex_order = [endpoints[0]]
        count = 0
        while duplicates and count < 1000:
            # 获取当前顶点关联的边
            current_vtx = f"{transform_node[0]}.vtx[{vertex_order[-1]}]"
            ve_list = cmds.polyInfo(current_vtx, ve=True)
            edge_nums = []
            parts = (ve_list[0].split(':')[1].split('\n')[0]).split(' ')
            for part in parts:
                num = ''.join([n for n in part.split('|')[-1] if n.isdigit()])
                if num:
                    edge_nums.append(num)

            # 找到下一条边
            next_edge = [g for g in edge_nums if g in edge_number_list][0]
            edge_number_list.remove(next_edge)

            # 找到下一个顶点
            edge_vtxs = cmds.polyInfo(f"{transform_node[0]}.e[{next_edge}]", ev=True)
            vtx_nums = []
            parts = (edge_vtxs[0].split(':')[1].split('\n')[0]).split(' ')
            for part in parts:
                num = ''.join([n for n in part.split('|')[-1] if n.isdigit()])
                if num:
                    vtx_nums.append(num)

            # 更新顶点顺序
            next_vtx = [g for g in vtx_nums if g in duplicates][0]
            duplicates.remove(next_vtx)
            vertex_order.append(next_vtx)
            count += 1

        # 处理开放/闭合边环的顶点列表
        if circle_state == 0 and len(endpoints) > 1:
            vertex_order.append(endpoints[1])
        else:
            # 移除闭合边环的重复顶点
            if vertex_order[0] == vertex_order[1]:
                vertex_order = vertex_order[1:]
            elif vertex_order[0] == vertex_order[-1]:
                vertex_order = vertex_order[:-1]

        # 格式化顶点路径
        final_vertices = [
            f"{transform_node[0]}.vtx[{v}]" for v in vertex_order
        ]
        return circle_state, final_vertices
######
    def updateBonMeshTool(self):
        # 获取Maya用户自定义脚本目录
        script_directory = cmds.internalVar(userScriptDir=True)
        print(f"脚本目录: {script_directory}")
        
        # 拼接完整路径
        full_path = os.path.join(script_directory, 'BonMeshTool')
        print(f"完整路径: {full_path}")
        
        # 初始化消息内容
        message = ""
        
        # 检查BonMeshTool文件夹是否存在
        if not os.path.exists(full_path):
            print("BonMeshTool 文件夹不存在")
            message = 'BonMeshTool 文件夹不存在，请自行检查'
        else:
            # 执行git pull命令
            try:
                print("执行 git pull 命令")
                result = subprocess.run(
                    ['git', '-C', full_path, 'pull'],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
        
                print(f"git pull 输出: {result.stdout}")
                print(f"git pull 错误: {result.stderr}")
                
                # 检查输出结果
                if "Already up to date." in result.stdout:
                    print("已经是最新的版本")
                    message = '已经是最新的版本'
                else:
                    print("更新成功")
                    message = '更新成功'
            
            except subprocess.CalledProcessError as e:
                print(f"更新失败: {e.stderr}")
                message = '更新失败'
    
        # 使用QTimer来延迟显示消息
        QTimer.singleShot(100, lambda: cmds.inViewMessage(amg=message, pos='midCenter', fade=True))
        
    def restore_window_settings(self):
        if cmds.optionVar(exists='BonMeshToolUI_width') and cmds.optionVar(exists='BonMeshToolUI_height'):
            self.resize(cmds.optionVar(q='BonMeshToolUI_width'), cmds.optionVar(q='BonMeshToolUI_height'))
        if cmds.optionVar(exists='BonMeshToolUI_position'):
            position = cmds.optionVar(q='BonMeshToolUI_position').split(',')
            self.move(int(position[0]), int(position[1]))

    def save_window_settings(self):
        cmds.optionVar(intValue=('BonMeshToolUI_width', self.width()))
        cmds.optionVar(intValue=('BonMeshToolUI_height', self.height()))
        position = '{},{}'.format(self.pos().x(), self.pos().y())
        cmds.optionVar(stringValue=('BonMeshToolUI_position', position))
        message = '<font color="#FFFF00"><b>保存成功！</b></font>窗口设置已保存。<font color="#FF69B4"><i>加油哦！</i></font>'
        cmds.inViewMessage(amg=message, pos='midCenter', fade=True)

    def RenameUVSetCmd(self, *args):
        selected_objects = cmds.ls(type='mesh')
        desired_name = self.rename_line_edit.text()
        for s_object in selected_objects:
            uv_ids = cmds.polyUVSet(s_object, query=True, allUVSetsIndices=True)
            for i in uv_ids:
                if i != 0:
                    cuvname = cmds.getAttr(f"{s_object}.uvSet[{i}].uvSetName")
                    cmds.polyUVSet(s_object, delete=True, uvSet=cuvname)
        for each_element in selected_objects:
            cuvname = cmds.getAttr(f"{each_element}.uvSet[0].uvSetName")
            if cuvname != desired_name:
                cmds.polyUVSet(each_element, rename=True, newUVSet=desired_name, uvSet=cuvname)
        cmds.inViewMessage(amg=f'重命名UV集为：{desired_name}', pos='midCenter', fade=True)


###
def show_bon_mesh_tool_ui():
    global bon_mesh_tool_ui
    try:
        bon_mesh_tool_ui.close()
        bon_mesh_tool_ui.deleteLater()
    except:
        pass
    bon_mesh_tool_ui = BonMeshToolUI()
    bon_mesh_tool_ui.show(dockable=True, area='right', allowedArea='all', width=330, height=400, floating=False)

def main():
    show_bon_mesh_tool_ui()

if __name__ == '__main__':
    main()
