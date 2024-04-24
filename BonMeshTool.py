# -*- coding: utf-8 -*-
##--------------------------------------------------------------------------
##
## 脚本名称 : BonMeshTool
## 作者    : 杨陶
## URL     : https://github.com/JaimeTao/BonModellingTool/tree/main
##E-mail  :taoyangfan@qq.com
## 更新时间 : 2024/04/24
##
##--------------------------------------------------------------------------
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2.QtWidgets import *
from PySide2.QtCore import *
import maya.cmds as cmds
import maya.mel as mel
import subprocess



class CollapsibleSection(QWidget):
    def __init__(self, title="", parent=None):
        super(CollapsibleSection, self).__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.toggle_button = QToolButton(text=title, checkable=True, checked=True)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
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
        selection_layout = QHBoxLayout()  # 创建水平布局
        select_uv_edges_button = QPushButton('选择UV边界')
        select_hard_edges_button = QPushButton('选择硬边')
        selection_layout.addWidget(select_uv_edges_button)
        selection_layout.addWidget(select_hard_edges_button)
        selection_widget.setLayout(selection_layout)  # 将布局设置到QWidget上
        selection_section.addWidget(selection_widget)  # 添加QWidget到CollapsibleSection
        self.layout().addWidget(selection_section)
        select_uv_edges_button.clicked.connect(self.SelUVBrodenEdgeCmd)# 匹配按钮
        select_hard_edges_button.clicked.connect(self.SelHardenEdgeCmd)# 匹配按钮
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
        slider_layout = QHBoxLayout()  # 使用水平布局来放置标签和滑动条
        # 创建显示滑动条值的标签，并设置初始文本
        self.value_label = QLabel("间隔数量: %d" % 1)  # 假设初始值为1
        # 创建和配置滑动条
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(1)  # 设置滑动条的最小值
        self.slider.setMaximum(20)  # 设置滑动条的最大值
        self.slider.setValue(1)  # 设置滑动条的初始值
        # 将标签和滑动条添加到水平布局中，标签在前
        slider_layout.addWidget(self.value_label)
        slider_layout.addWidget(self.slider)
        # 连接滑动条的信号到一个槽函数以更新标签
        self.slider.valueChanged.connect(self.slider_value_changed)
        slider_widget.setLayout(slider_layout)  # 设置布局到QWidget
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        to_rings_button = QPushButton('到平行边')
        ring_loop_button = QPushButton('到环形边')
        delete_edges_button = QPushButton('删除环边')
        button_layout.addWidget(to_rings_button)
        button_layout.addWidget(ring_loop_button)
        button_layout.addWidget(delete_edges_button)
        button_widget.setLayout(button_layout)
        # 连接按钮到函数
        to_rings_button.clicked.connect(self.ToRingsCmd)
        ring_loop_button.clicked.connect(self.RingLoopCmd)
        delete_edges_button.clicked.connect(self.DeleteEdgesCmd)
        interval_section.addWidget(slider_widget)
        interval_section.addWidget(button_widget)
        self.layout().addWidget(interval_section)


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
        interval_section.addWidget(slider_widget)
        interval_section.addWidget(button_widget)
        # Update the layout to include the new section
        self.layout().addWidget(Bridge_section)



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

    def SelUVBrodenEdgeCmd(self, *args):
        selection = cmds.ls(sl=True, l=True)
        mesh_edges = []
        uv_border_edges = []
        for s in selection:
            try:
                mesh_edges.extend(cmds.ls(cmds.polyListComponentConversion(s, te=True), fl=True, l=True))
            except:
                pass
        if mesh_edges:
            for e in mesh_edges:
                edge_uvs = cmds.ls(cmds.polyListComponentConversion(e, tuv=True), fl=True)
                edge_faces = cmds.ls(cmds.polyListComponentConversion(e, tf=True), fl=True)
                if len(edge_uvs) > 2:
                    uv_border_edges.append(e)
                elif len(edge_faces) < 2:
                    uv_border_edges.append(e)
        if uv_border_edges:
            cmds.select(uv_border_edges)
    def SelHardenEdgeCmd (self, *args):
        cmds.polySelectConstraint(m=3, t=0x8000, sm=1)
        cmds.polySelectConstraint(m=0)

    def TranPositoUVCmd (self, *args):
        cmds.transferAttributes(transferUVs=1,sampleSpace=1,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def TranUVtoPosiCmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=3,searchMethod=3,)
        cmds.delete(constructionHistory=True)
        
    def TranPositoBordenECmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=0,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def slider_value_changed(self, value):
        self.value_label.setText("间隔数量: %d" % value)

    def get_current_slider_value(self):
        current_value = self.slider.value()
        print("Current slider value:", current_value)
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
        current_value = self.get_current_slider_value()
        n = edge_count + current_value
        mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        mel.eval('polySelectEdgesEveryN("edgeLoop", 0)',0)

    def RingLoopCmd(self):
        edge_count = self.get_selected_edge_count()
        current_value = self.get_current_slider_value()
        n = edge_count + current_value
        mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')

    def DeleteEdgesCmd(self):
        edge_count = self.get_selected_edge_count()
        current_value = self.get_current_slider_value()
        n = edge_count + current_value
        mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')
        mel.eval('DeleteEdge')
###
    def update_path(self):
        new_path = self.Bridge_Dir_line_edit.text()
        cmds.optionVar(sv=("RizomUVPath", new_path))
        self.write_loader()
        
    def setup_dirs(self):
        self.ObjectType = 'fbx'
        self.MayaScriptDir = cmds.internalVar(userScriptDir=True)
        self.BridgeDir = self.MayaScriptDir + 'BonModelingTool/'
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
###
def show_bon_modeling_tool_ui():
    global bon_modeling_tool_ui
    try:
        bon_modeling_tool_ui.close()
        bon_modeling_tool_ui.deleteLater()
    except:
        pass

    bon_modeling_tool_ui = BonModelingToolUI()
    bon_modeling_tool_ui.show(dockable=True, area='right', allowedArea='all', width=330, height=400, floating=False)

def main():
    global bon_mesh_tool_ui
    try:
        bon_mesh_tool_ui.close()
        bon_mesh_tool_ui.deleteLater()
    except:
        pass
    bon_mesh_tool_ui = BonMeshToolUI()
    bon_mesh_tool_ui.show(dockable=True, area='right', allowedArea='all', width=330, height=400, floating=False)

if __name__ == '__main__':
    main()
