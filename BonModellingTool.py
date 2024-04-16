# -*- coding: utf-8 -*-
##--------------------------------------------------------------------------
##
## 脚本名称 : Edges select tool
## 作者    : 杨陶
## URL     : https://space.bilibili.com/488687065?spm_id_from=333.1007.0.0
## 更新时间 : 2024/04/15
##
##--------------------------------------------------------------------------
import maya.cmds as cmds
import maya.mel as mel

class Bon_ModellingTool(object):    
    def __init__(self):        
        self.window = 'BonModellingTool'
        self.title = 'BonModellingTool'
        self.size = (330,400)

    def create(self):
        if cmds.window('BonModellingTool', exists=True):
            cmds.deleteUI('BonModellingTool', window=True)
        self.window = cmds.window(
            self.window,
            t=self.title,
            widthHeight=self.size
        )
        self.layout()
        cmds.showWindow()    

    def layout(self):
        self.formLayout01 = cmds.formLayout(nd=100)
        self.description01 = cmds.text(l='为场景中所有默认UV集重命名，并删除多余UV集！', al='left')
        self.buttonRenameUVSet = cmds.button(l='重命名', c=self.RenameUVSetCmd)
        self.name_input = cmds.textField(text='map1')
        self.separator01 = cmds.separator(st='in')
        self.description02 = cmds.text(l='修改三角形分割方式', al='left')
        self.displayquadSplit = cmds.checkBox(l='显示三角分割', changeCommand=self.DisplayTriangle)
        self.buttonMayaTriangle = cmds.button(l='切换到maya三角分割', c=self.mayaTriangleCmd)
        self.buttonUnityTriangle = cmds.button(l='切换到unity三角分割', c=self.unityTriangleCmd)
        self.buttonUnlockNormal = cmds.button(l='解锁法线', c=self.UnlockNormalCmd)
        self.buttonSoftenEdge = cmds.button(l='软边', c=self.SoftenEdgeCmd)
        self.buttonHardenEdge = cmds.button(l='硬边', c=self.HardenEdgeCmd)
        self.separator02 = cmds.separator(st='in')
        self.description03 = cmds.text(l='快速选择工具', al='left')
        self.buttonSelUVBrodenEdge = cmds.button(l='选择UV边界', c=self.SelUVBrodenEdgeCmd)
        self.buttonSelHardenEdge = cmds.button(l='选择硬边', c=self.SelHardenEdgeCmd)
        self.separator03 = cmds.separator(st='in')
        self.description04 = cmds.text(l='传递属性工具', al='left')
        self.buttonTranPositoUV = cmds.button(l='位置toUV', c=self.TranPositoUVCmd)
        self.buttonTranUVtoPosi = cmds.button(l='UVto位置', c=self.TranUVtoPosiCmd)
        self.buttonTranPositoBordenE = cmds.button(l='边界to边界', c=self.TranPositoBordenECmd)
        self.separator04 = cmds.separator(st='in')
        self.description05 = cmds.text(l='间隔选择工具', al='left')
        self.bottonNumOfEveryN = cmds.intSliderGrp(field = True, label = '间隔数量',minValue=1, maxValue=10,  value=1)
        self.buttonToRings = cmds.button(l='到平行边', c=self.ToRingsCmd)
        self.buttonRingLoop = cmds.button(l='到环形边', c=self.RingLoopCmd)
        self.buttonDeleteEdges = cmds.button(l='删除环边', c=self.DeleteEdgesCmd)
        self.buttonClose = cmds.button(l='Close', c=('cmds.deleteUI("' + self.window + '")'))
        cmds.formLayout(self.formLayout01, edit=True,\
            attachPosition=(
                #description01
                (self.description01, 'top', 5,0),\
                (self.description01, 'left', 5,0),\
                (self.description01, 'bottom', 0,5),\
                (self.description01, 'right', 5,100),\
                #renameButton
                (self.buttonRenameUVSet, 'top', 5,5),\
                (self.buttonRenameUVSet, 'left', 5,0),\
                (self.buttonRenameUVSet, 'bottom', 0,15),\
                (self.buttonRenameUVSet, 'right', 5,50),\
                #rename_input
                (self.name_input, 'top', 5,5),\
                (self.name_input, 'left', 5,50),\
                (self.name_input, 'bottom', 0,15),\
                (self.name_input, 'right', 5,100),\
                #separator01
                (self.separator01, 'top', 2,15),\
                (self.separator01, 'left', 5,0),\
                (self.separator01, 'bottom', 2,16),\
                (self.separator01, 'right', 5,100),\
                #description02
                (self.description02, 'top', 0,16),\
                (self.description02, 'left', 5,0),\
                (self.description02, 'bottom', 0,21),\
                (self.description02, 'right', 5,100),\
                #displayquadSplit
                (self.displayquadSplit, 'top', 5,16),\
                (self.displayquadSplit, 'left', 5,0),\
                (self.displayquadSplit, 'bottom', 5,31),\
                (self.displayquadSplit, 'right', 5,100),\
                #buttonMayaTriangle
                (self.buttonMayaTriangle, 'top', 5,26),\
                (self.buttonMayaTriangle, 'left', 5,50),\
                (self.buttonMayaTriangle, 'bottom', 5,36),\
                (self.buttonMayaTriangle, 'right', 5,100),\
                #buttonUnityTriangle
                (self.buttonUnityTriangle, 'top', 5,37),\
                (self.buttonUnityTriangle, 'left', 5,50),\
                (self.buttonUnityTriangle, 'bottom', 5,45),\
                (self.buttonUnityTriangle, 'right', 5,100),\
                #解锁法线
                (self.buttonUnlockNormal, 'top', 5,26),\
                (self.buttonUnlockNormal, 'left', 5,0),\
                (self.buttonUnlockNormal, 'bottom', 5,31),\
                (self.buttonUnlockNormal, 'right', 5,50),\
                #buttonSoftenEdge
                (self.buttonSoftenEdge, 'top', 5,33),\
                (self.buttonSoftenEdge, 'left', 5,0),\
                (self.buttonSoftenEdge, 'bottom', 5,38),\
                (self.buttonSoftenEdge, 'right', 5,50),\
                #buttonHardenEdge
                (self.buttonHardenEdge, 'top', 5,40),\
                (self.buttonHardenEdge, 'left', 5,0),\
                (self.buttonHardenEdge, 'bottom', 5,45),\
                (self.buttonHardenEdge, 'right', 5,50),\
                #separator02
                (self.separator02, 'top', 2,47),\
                (self.separator02, 'left', 5,0),\
                (self.separator02, 'bottom', 2,47),\
                (self.separator02, 'right', 5,100),\
                #description03
                (self.description03, 'top', 0,48),\
                (self.description03, 'left', 5,0),\
                (self.description03, 'bottom', 0,50),\
                (self.description03, 'right', 5,100),\
                #buttonSelUVBrodenEdge
                (self.buttonSelUVBrodenEdge, 'top', 5,52),\
                (self.buttonSelUVBrodenEdge, 'left', 5,0),\
                (self.buttonSelUVBrodenEdge, 'bottom', 5,57),\
                (self.buttonSelUVBrodenEdge, 'right', 5,50),\
                #buttonSelUVHardenEdge
                (self.buttonSelHardenEdge, 'top', 5,52),\
                (self.buttonSelHardenEdge, 'left', 5,50),\
                (self.buttonSelHardenEdge, 'bottom', 5,57),\
                (self.buttonSelHardenEdge, 'right', 5,100),\
                #separator03
                (self.separator03, 'top', 2,59),\
                (self.separator03, 'left', 5,0),\
                (self.separator03, 'bottom', 2,60),\
                (self.separator03, 'right', 5,100),\
                #description04
                (self.description04, 'top', 0,60),\
                (self.description04, 'left', 5,0),\
                (self.description04, 'bottom', 0,60),\
                (self.description04, 'right', 5,100),\
                #buttonTranPositoUV
                (self.buttonTranPositoUV, 'top', 5,63),\
                (self.buttonTranPositoUV, 'left', 5,0),\
                (self.buttonTranPositoUV, 'bottom', 5,70),\
                (self.buttonTranPositoUV, 'right', 5,33),\
                #buttonTranUVtoPosi
                (self.buttonTranUVtoPosi, 'top', 5,63),\
                (self.buttonTranUVtoPosi, 'left', 5,33),\
                (self.buttonTranUVtoPosi, 'bottom', 5,70),\
                (self.buttonTranUVtoPosi, 'right', 5,66),\
                #buttonTranPositoBordenE
                (self.buttonTranPositoBordenE, 'top', 5,63),\
                (self.buttonTranPositoBordenE, 'left', 5,66),\
                (self.buttonTranPositoBordenE, 'bottom', 5,70),\
                (self.buttonTranPositoBordenE, 'right', 5,100),\
                #separator04
                (self.separator04, 'top', 2,70),\
                (self.separator04, 'left', 5,0),\
                (self.separator04, 'bottom', 2,71),\
                (self.separator04, 'right', 5,100),\
                #description05
                (self.description05, 'top', 0,71),\
                (self.description05, 'left', 5,0),\
                (self.description05, 'bottom', 0,72),\
                (self.description05, 'right', 5,100),\
                #bottonNumOfEveryN
                (self.bottonNumOfEveryN, 'top', 5,74),\
                (self.bottonNumOfEveryN, 'left', 0,0),\
                (self.bottonNumOfEveryN, 'bottom', 5,77),\
                (self.bottonNumOfEveryN, 'right', 0,30),\
                #buttonToRings
                (self.buttonToRings, 'top', 5,81),\
                (self.buttonToRings, 'left', 5,0),\
                (self.buttonToRings, 'bottom', 5,87),\
                (self.buttonToRings, 'right', 5,33),\
                #buttonRingLoop
                (self.buttonRingLoop, 'top', 5,81),\
                (self.buttonRingLoop, 'left', 5,33),\
                (self.buttonRingLoop, 'bottom', 5,87),\
                (self.buttonRingLoop, 'right', 5,66),\
                #buttonDeleteEdges
                (self.buttonDeleteEdges, 'top', 5,81),\
                (self.buttonDeleteEdges, 'left', 5,66),\
                (self.buttonDeleteEdges, 'bottom', 5,87),\
                (self.buttonDeleteEdges, 'right', 5,100),\
                #buttonClose               
                (self.buttonClose, 'top', 5,90),\
                (self.buttonClose, 'left', 5,0),\
                (self.buttonClose, 'bottom', 5,100),\
                (self.buttonClose, 'right', 5,100)
            )
        )
    def RenameUVSetCmd(self,*args):
        selectedObjects = cmds.ls(type='mesh')
        for sObject in selectedObjects:
            uv_ids = cmds.polyUVSet(sObject, query=True, allUVSetsIndices=True)
            for i in uv_ids:
                if i != 0:
                    cuvname = cmds.getAttr(f"{sObject}.uvSet[{i}].uvSetName")
                    cmds.polyUVSet(sObject, delete=True, uvSet=cuvname)
        sel = cmds.ls(type='mesh')
        for eachElement in sel:
            cuvname = cmds.getAttr(f"{eachElement}.uvSet[0].uvSetName")
            desired_name = cmds.textField(self.name_input, query=True, text=True)
            if cuvname != desired_name:
                cmds.polyUVSet(eachElement, rename=True, newUVSet=desired_name, uvSet=cuvname)
        cmds.warning("重命名UV集为：",desired_name)

    def DisplayTriangle(self,*args):
        isChecked = cmds.checkBox(self.displayquadSplit, query=True, value=True)
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
        mds.transferAttributes(transferPositions=1,sampleSpace=3,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def TranUVtoPosiCmd (self, *args):
        cmds.transferAttributes(transferPositions=0,transferUVs=2,sampleSpace=1,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def TranPositoBordenECmd (self, *args):
        cmds.transferAttributes(transferPositions=1,sampleSpace=1,searchMethod=3,)
        cmds.delete(constructionHistory=True)

    def get_current_slider_value(self,*args):
        current_value = cmds.intSliderGrp(self.bottonNumOfEveryN, query=True, value=True)
        print("Current slider value:", current_value)
        return current_value

    def get_selected_edge_count(self,*args):
        selection = cmds.ls(selection=True, flatten=True)
        edge_count = 0
        for item in selection:
            if '.e[' in item:
                edge_count += 1
        print("Selected edge count:", edge_count)
        return edge_count

    def ToRingsCmd(self,*args):
        edge_count = self.get_selected_edge_count()
        current_value = self.get_current_slider_value()
        n = edge_count + current_value
        mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        mel.eval('polySelectEdgesEveryN("edgeLoop", 0)',0)

    def RingLoopCmd(self,*args):
        edge_count = self.get_selected_edge_count()
        current_value = self.get_current_slider_value()
        n = edge_count + current_value
        mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')

    def DeleteEdgesCmd(self,*args):
        edge_count = self.get_selected_edge_count()
        current_value = self.get_current_slider_value()
        n = edge_count + current_value
        mel.eval('polySelectEdgesEveryN("edgeRing", {0})'.format(n))
        mel.eval('polySelectEdgesEveryN("edgeLoop", 1)')
        mel.eval('DeleteEdge')
        
def main():
    BonModellingToolWindow = Bon_ModellingTool()
    BonModellingToolWindow.create()
