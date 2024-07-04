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
##--------------------------------------------------------------------------
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2.QtWidgets import *
from PySide2.QtCore import *
import maya.cmds as cmds
import maya.mel as mel
import subprocess
import os

def save_settings(key_name, value):
    cmds.optionVar(stringValue=(key_name, str(value)))

def load_settings(key_name, default_value=''):
    if cmds.optionVar(exists=key_name):
        return cmds.optionVar(query=key_name)
    return default_value

class CollapsibleSection(QWidget):
    def __init__(self, title="", parent=None):
        super(CollapsibleSection, self).__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.toggle_button = QToolButton(text=title, checkable=True, checked=True)
        self.toggle_button.setStyleSheet("QToolButton { border: none; padding-top: 3px; padding-bottom: 3px; color: #bbbbbb; font-weight: bold; background-color: #3c3c3c; font-size: 18px;}")
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
        self.setWindowTitle('BonMeshTool')
        self.window_name = 'BonMeshToolUI'
        # 加载窗口设置
        self.restore_window_settings()
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.setup_dirs()
        
        self.setMinimumWidth(250)
        self.setMinimumHeight(400)
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.setup_dirs()

        # Section for UV renaming
        uv_section = CollapsibleSection("重命名并删除多余UV集！")
        rename_widget = QWidget()  # 创建一个新的QWidget
        rename_layout = QHBoxLayout()  # 创建水平布局
        self.rename_button = QPushButton('重命名')
        self.rename_line_edit = QLineEdit('map1')
        rename_layout.addWidget(self.rename_button)
        rename_layout.addWidget(self.rename_line_edit)
        rename_widget.setLayout(rename_layout)  # 将布局设置到QWidget上
        uv_section.addWidget(rename_widget)  # 添加QWidget到CollapsibleSection
        self.layout().addWidget(uv_section)
        self.rename_button.clicked.connect(self.RenameUVSetCmd)# 匹配按钮

        # Section for triangle operation
        triangle_section = CollapsibleSection("修改三角形分割方式")
        # 添加显示三角分割的复选框
        self.display_triangle_checkbox = QCheckBox('显示三角分割')
        triangle_section.addWidget(self.display_triangle_checkbox)
        self.display_triangle_checkbox.stateChanged.connect(self.DisplayTriangle)# 匹配按钮
        # 创建第一行的QWidget和布局
        triangle_row1_widget = QWidget()
        triangle_row1_layout = QHBoxLayout()
        # 创建按钮
        maya_button = QPushButton('切换到maya三角分割')
        unity_button = QPushButton('切换到unity三角分割')
        maya_button.clicked.connect(self.mayaTriangleCmd)# 匹配按钮
        unity_button.clicked.connect(self.unityTriangleCmd)# 匹配按钮
        # 设置按钮高度是默认的两倍
        maya_button.setMinimumHeight(maya_button.sizeHint().height() * 2)
        unity_button.setMinimumHeight(unity_button.sizeHint().height() * 2)
        # 将按钮添加到布局
        triangle_row1_layout.addWidget(maya_button)
        triangle_row1_layout.addWidget(unity_button)
        # 设置布局到QWidget
        triangle_row1_widget.setLayout(triangle_row1_layout)
        # 添加到CollapsibleSection
        triangle_section.addWidget(triangle_row1_widget)

        # 创建第二行的QWidget和布局
        triangle_row2_widget = QWidget()
        triangle_row2_layout = QHBoxLayout()
        # 创建按钮
        unlock_button = QPushButton('解锁法线')
        soft_button = QPushButton('软边')
        hard_button = QPushButton('硬边')
        # 将按钮添加到布局
        triangle_row2_layout.addWidget(unlock_button)
        triangle_row2_layout.addWidget(soft_button)
        triangle_row2_layout.addWidget(hard_button)
        unlock_button.clicked.connect(self.UnlockNormalCmd)# 匹配按钮
        soft_button.clicked.connect(self.SoftenEdgeCmd)# 匹配按钮
        hard_button.clicked.connect(self.HardenEdgeCmd)# 匹配按钮
        # 设置布局到QWidget
        triangle_row2_widget.setLayout(triangle_row2_layout)
        # 添加到CollapsibleSection
        triangle_section.addWidget(triangle_row2_widget)
        # 将整个CollapsibleSection添加到主布局
        self.layout().addWidget(triangle_section)
        # Section for quick selection tools
        selection_section = CollapsibleSection("快速选择工具")
        selection_widget = QWidget()  # 创建一个新的QWidget
        selection_layout = QVBoxLayout()  # 创建垂直布局，用于将按钮分成两行
        # 第一行布局，包含“选择UV边界”和“选择硬边”按钮
        first_row_layout = QHBoxLayout()
        select_uv_edges_button = QPushButton('选择UV边界')
        select_hard_edges_button = QPushButton('选择硬边')
        first_row_layout.addWidget(select_uv_edges_button)
        first_row_layout.addWidget(select_hard_edges_button)
        # 第二行布局，包含“存储选择边”和“选择存储边”按钮
        second_row_layout = QHBoxLayout()
        store_edges_button = QPushButton('存储选择边')
        select_stored_edges_button = QPushButton('选择存储边')
        second_row_layout.addWidget(store_edges_button)
        second_row_layout.addWidget(select_stored_edges_button)
        # 将两个行布局添加到主垂直布局
        selection_layout.addLayout(first_row_layout)
        selection_layout.addLayout(second_row_layout)
        # 将布局设置到QWidget上
        selection_widget.setLayout(selection_layout)
        selection_section.addWidget(selection_widget)  # 添加QWidget到CollapsibleSection
        self.layout().addWidget(selection_section)
        # 绑定按钮到函数
        select_uv_edges_button.clicked.connect(self.SelUVBrodenEdgeCmd)  # 绑定选择UV边界按钮到函数
        select_hard_edges_button.clicked.connect(self.SelHardenEdgeCmd)  # 绑定选择硬边按钮到函数
        store_edges_button.clicked.connect(self.store_selected_edges)  # 绑定存储选择边按钮到函数
        select_stored_edges_button.clicked.connect(self.select_stored_edges)  # 绑定选择存储边按钮到函数
        # Section for transferring attributes
        transfer_section = CollapsibleSection("传递属性工具")
        transfer_widget = QWidget()  # 创建一个新的QWidget
        transfer_layout = QHBoxLayout()  # 创建水平布局
        # 创建按钮并连接到对应的函数
        transfer_pos_to_uv_button = QPushButton('位置toUV')
        transfer_uv_to_pos_button = QPushButton('UVto位置')
        transfer_pos_to_border_button = QPushButton('边界to边界')
        # 连接按钮到函数
        transfer_pos_to_uv_button.clicked.connect(self.TranPositoUVCmd)
        transfer_uv_to_pos_button.clicked.connect(self.TranUVtoPosiCmd)
        transfer_pos_to_border_button.clicked.connect(self.TranPositoBordenECmd)
        # 将按钮添加到布局
        transfer_layout.addWidget(transfer_pos_to_uv_button)
        transfer_layout.addWidget(transfer_uv_to_pos_button)
        transfer_layout.addWidget(transfer_pos_to_border_button)

        '''快速选择部分'''
        # 设置布局到QWidget
        transfer_widget.setLayout(transfer_layout)

        # 添加QWidget到CollapsibleSection
        transfer_section.addWidget(transfer_widget)

        # 将transfer_section添加到主布局
        self.layout().addWidget(transfer_section)

        # Section for interval selection tools
        interval_section = CollapsibleSection("间隔选择工具")

        # 为滑动条和值标签创建一个独立的QWidget
        slider_widget = QWidget()
        slider_layout = QVBoxLayout()  # 使用垂直布局来放置多个水平布局

        # 间隔数量滑动条的布局
        interval_slider_layout = QHBoxLayout()  # 使用水平布局来放置标签和滑动条

        # 创建显示间隔数量滑动条值的标签，并设置初始文本
        self.Ring_value_label = QLabel("Ring间隔数: %d" % 1)  # 假设初始值为1

        # 创建和配置间隔数量滑动条
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)  # 设置滑动条的最小值
        self.slider.setMaximum(20)  # 设置滑动条的最大值
        self.slider.setValue(1)  # 设置滑动条的初始值

        # 将标签和滑动条添加到水平布局中，标签在前
        interval_slider_layout.addWidget(self.Ring_value_label)
        interval_slider_layout.addWidget(self.slider)

        # 连接滑动条的信号到一个槽函数以更新标签
        self.slider.valueChanged.connect(self.Ring_slider_value_changed)

        # 将间隔数量滑动条的布局添加到主滑动条布局
        slider_layout.addLayout(interval_slider_layout)

        # Loop滑动条的布局
        loop_slider_layout = QHBoxLayout()  # 使用水平布局来放置标签和滑动条

        # 创建显示loop滑动条值的标签，并设置初始文本
        self.loop_value_label = QLabel("loop间隔数: %d" % 0)  # 假设初始值为0

        # 创建和配置loop滑动条
        self.loop_slider = QSlider(Qt.Horizontal)
        self.loop_slider.setMinimum(0)  # 设置滑动条的最小值
        self.loop_slider.setMaximum(20)  # 设置滑动条的最大值
        self.loop_slider.setValue(0)  # 设置滑动条的初始值

        # 将标签和滑动条添加到水平布局中，标签在前
        loop_slider_layout.addWidget(self.loop_value_label)
        loop_slider_layout.addWidget(self.loop_slider)

        # 连接loop滑动条的信号到一个槽函数以更新标签
        self.loop_slider.valueChanged.connect(self.loop_slider_value_changed)

        # 将loop滑动条的布局添加到主滑动条布局
        slider_layout.addLayout(loop_slider_layout)

        # 设置滑动条布局到QWidget
        slider_widget.setLayout(slider_layout)

        # 创建和配置按钮的布局
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        to_rings_button = QPushButton('间隔选择')
        Extend_to_Ring_button = QPushButton('Ring延伸')
        Extend_to_Loops_button = QPushButton('Loop延伸')

        button_layout.addWidget(to_rings_button)
        button_layout.addWidget(Extend_to_Ring_button)
        button_layout.addWidget(Extend_to_Loops_button)

        button_widget.setLayout(button_layout)

        # 连接按钮到函数
        to_rings_button.clicked.connect(self.ToRingsCmd)
        Extend_to_Ring_button.clicked.connect(self.Extend_to_RingCmd)
        Extend_to_Loops_button.clicked.connect(self.Extend_to_LoopCmd)
        
        # 将滑动条和按钮的Widget添加到间隔选择工具的section中
        interval_section.addWidget(slider_widget)
        interval_section.addWidget(button_widget)

        # 将间隔选择工具的section添加到主布局
        self.layout().addWidget(interval_section)
        '''快速选择部分'''
        #Section for RizomUV Bridge
        Bridge_section = CollapsibleSection("RizomUV Bridge")
        Bridge_Dir_widget = QWidget()  # 创建一个新的QWidget
        Bridge_Dir_layout = QHBoxLayout()  # 创建水平布局
        Bridge_Dir_button = QPushButton('更新路径')
        self.Bridge_Dir_line_edit = QLineEdit()  # 保存引用
        if cmds.optionVar(exists="RizomUVPath"):
            self.Bridge_Dir_line_edit.setText(cmds.optionVar(q="RizomUVPath"))
        else:
            self.Bridge_Dir_line_edit.setText(r'C:\Program Files\Rizom Lab\RizomUV 2023.0\rizomuv.exe')
        Bridge_Dir_layout.addWidget(Bridge_Dir_button)
        Bridge_Dir_layout.addWidget(self.Bridge_Dir_line_edit)
        Bridge_Dir_widget.setLayout(Bridge_Dir_layout)  # 将布局设置到QWidget上
        Bridge_section.addWidget(Bridge_Dir_widget)  # 添加QWidget到CollapsibleSection
        self.layout().addWidget(Bridge_section)
        Bridge_Dir_button.clicked.connect(self.update_path)

        # New section with three horizontally distributed buttons in a second row
        button_row_widget = QWidget()
        button_row_layout = QHBoxLayout()
        export_button = QPushButton('导出')
        import_button = QPushButton('导入')
        launch_button = QPushButton('启动RizomUV')
        button_row_layout.addWidget(export_button)
        button_row_layout.addWidget(import_button)
        button_row_layout.addWidget(launch_button)
        button_row_widget.setLayout(button_row_layout)
        Bridge_section.addWidget(button_row_widget)  # 添加到同一个CollapsibleSection
        export_button.clicked.connect(self.export_obj)
        import_button.clicked.connect(self.import_obj)
        launch_button.clicked.connect(self.launch_rizom)
        # Update the layout to include the new section
        self.layout().addWidget(Bridge_section)

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
        self.save_settings_button.clicked.connect(self.saveWindowSettings)

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
            cmds.inViewMessage(amg='没有选择任何对象!', pos='midCenter', fade=True)
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
    def store_selected_edges(self, *args):        
        global stored_edges
        selected_edges = cmds.ls(selection=True, flatten=True)

        if not selected_edges:
            cmds.warning("请选择一些边来存储。")
            return

        stored_edges = selected_edges
        print(f"存储了 {len(stored_edges)} 条边。")

    def select_stored_edges(self, *args):


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

    def loop_slider_value_changed(self, value):
        self.loop_value_label.setText("loop间隔数: %d" % value)

    def get_current_Ring_slider_value(self):
        current_value = self.slider.value()
        print("Current slider value:", current_value)
        return current_value
##11
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

    def ToRingsCmd(self):
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
            
    def Extend_to_RingCmd(self):
        mel.eval('polySelectEdgesEveryN("edgeRing", 1)')
        
    def Extend_to_LoopCmd(self):
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')
        
###
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

    def saveWindowSettings(self):
        message = '<font color="#FFFF00"><b>别急！</b></font>该有的总会有的！这个功能暂时没有实现。<font color="#FF69B4">🏖️🥼🥻🥾🎧️🛋️<i>好好做模型，加油哦！</i></font>'
        cmds.inViewMessage(amg=message, pos='midCenter', fade=True)
    ''' 默认占位的保存窗口设置函数'''
            
    def restore_window_settings(self):
        # 窗口大小
        width = int(load_settings(self.window_name + '_width', 250))
        height = int(load_settings(self.window_name + '_height', 400))
        self.resize(width, height)
            
    def save_window_settings(self):
        # 保存窗口大小
        width = self.width()
        height = self.height()
        save_settings(self.window_name + '_width', width)
        save_settings(self.window_name + '_height', height)
        
        # 保存窗口位置
        pos = self.pos()
        save_settings(self.window_name + '_position', '{},{}'.format(pos.x(), pos.y()))

    def closeEvent(self, event):
        self.save_window_settings()
        super(BonMeshToolUI, self).closeEvent(event)

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
