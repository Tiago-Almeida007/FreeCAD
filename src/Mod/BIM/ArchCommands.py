# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2011 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

__title__  = "FreeCAD Arch Commands"
__author__ = "Yorik van Havre"
__url__    = "https://www.freecad.org"

## @package ArchCommands
#  \ingroup ARCH
#  \brief Utility functions for the Arch Workbench
#
#  This module provides general functions used by Arch tools
#  and utility commands

import FreeCAD
import ArchComponent
import Draft
import DraftVecUtils

from FreeCAD import Vector
from draftutils import params

if FreeCAD.GuiUp:
    from PySide import QtGui,QtCore
    import FreeCADGui
    from draftutils.translate import translate
else:
    # \cond
    def translate(ctxt,txt):
        return txt
    # \endcond


# module functions ###############################################

def getStringList(objects):
    '''getStringList(objects): returns a string defining a list
    of objects'''
    result = "["
    for o in objects:
        if len(result) > 1:
            result += ","
        result += "FreeCAD.ActiveDocument." + o.Name
    result += "]"
    return result

def getDefaultColor(objectType):
    '''getDefaultColor(string): returns a color value for the given object
    type (Wall, Structure, Window, WindowGlass)'''
    alpha = 1.0
    if objectType == "Wall":
        c = params.get_param_arch("WallColor")
    elif objectType == "Structure":
        c = params.get_param_arch("StructureColor")
    elif objectType == "WindowGlass":
        c = params.get_param_arch("WindowGlassColor")
        alpha = 1.0 - params.get_param_arch("WindowTransparency") / 100.0
    elif objectType == "Rebar":
        c = params.get_param_arch("RebarColor")
    elif objectType == "Panel":
        c = params.get_param_arch("PanelColor")
    elif objectType == "Space":
        c = params.get_param_arch("defaultSpaceColor")
    elif objectType == "Helpers":
        c = params.get_param_arch("ColorHelpers")
    elif objectType == "Construction":
        c = params.get_param("constructioncolor")
        alpha = 0.2
    else:
        c = params.get_param_view("DefaultShapeColor")
    r, g, b, _ = Draft.get_rgba_tuple(c)
    return (r, g, b, alpha)

def addComponents(objectsList,host):
    '''addComponents(objectsList,hostObject): adds the given object or the objects
    from the given list as components to the given host Object. Use this for
    example to add windows to a wall, or to add walls to a cell or floor.'''
    if not isinstance(objectsList,list):
        objectsList = [objectsList]
    hostType = Draft.getType(host)
    if hostType in ["Floor","Building","Site","Project","BuildingPart"]:
        for o in objectsList:
            host.addObject(o)
    elif hostType in ["Wall","CurtainWall","Structure","Precast","Window","Roof","Stairs","StructuralSystem","Panel","Component","Pipe"]:
        import DraftGeomUtils
        a = host.Additions
        if hasattr(host,"Axes"):
            x = host.Axes
        for o in objectsList:
            if hasattr(o,'Shape'):
                if Draft.getType(o) == "Window":
                    if hasattr(o,"Hosts"):
                        if not host in o.Hosts:
                            g = o.Hosts
                            g.append(host)
                            o.Hosts = g
                elif DraftGeomUtils.isValidPath(o.Shape) and (hostType in ["Structure","Precast"]):
                    if o.AttachmentSupport == host:
                        o.AttachmentSupport = None
                    host.Tool = o
                elif Draft.getType(o) == "Axis":
                    if not o in x:
                        x.append(o)
                elif not o in a:
                    if hasattr(o,"Shape"):
                        a.append(o)
        host.Additions = a
        if hasattr(host,"Axes"):
            host.Axes = x
    elif hostType in ["SectionPlane"]:
        a = host.Objects
        for o in objectsList:
            if not o in a:
                a.append(o)
        host.Objects = a
    elif host.isDerivedFrom("App::DocumentObjectGroup"):
        for o in objectsList:
            host.addObject(o)

def removeComponents(objectsList,host=None):
    '''removeComponents(objectsList,[hostObject]): removes the given component or
    the components from the given list from their parents. If a host object is
    specified, this function will try adding the components as holes to the host
    object instead.'''
    if not isinstance(objectsList,list):
        objectsList = [objectsList]
    if host:
        if Draft.getType(host) in ["Wall","CurtainWall","Structure","Precast","Window","Roof","Stairs","StructuralSystem","Panel","Component","Pipe"]:
            if hasattr(host,"Tool"):
                if objectsList[0] == host.Tool:
                    host.Tool = None
            if hasattr(host,"Axes"):
                a = host.Axes
                for o in objectsList[:]:
                    if o in a:
                        a.remove(o)
                        objectsList.remove(o)
            s = host.Subtractions
            for o in objectsList:
                if Draft.getType(o) == "Window":
                    if hasattr(o,"Hosts"):
                        if not host in o.Hosts:
                            g = o.Hosts
                            g.append(host)
                            o.Hosts = g
                elif not o in s:
                    s.append(o)
                    if FreeCAD.GuiUp:
                        if not Draft.getType(o) in ["Window","Roof"]:
                            setAsSubcomponent(o)
                    # Making reference to BimWindow.Arch_Window:
                    # Check if o and o.Base has Attachment Support, and
                    # if the support is the host object itself - thus a cyclic
                    # dependency and probably creating TNP.
                    # If above is positive, remove its AttachmentSupport:
                    if hasattr(o,"Base") and o.Base:
                        objList = [o, o.Base]
                    else:
                        objList = [o]
                    for i in objList:
                        objHost = None
                        if hasattr(i,"AttachmentSupport"):
                            if i.AttachmentSupport:
                                if isinstance(i.AttachmentSupport,tuple):
                                    objHost = i.AttachmentSupport[0]
                                elif isinstance(i.AttachmentSupport,list):
                                    objHost = i.AttachmentSupport[0][0]
                                else:
                                    objHost = i.AttachmentSupport
                            if objHost == host:
                                msg = FreeCAD.Console.PrintMessage
                                msg(i.Label + " is mapped to " + host.Label +
                                    ", removing the former's Attachment " +
                                    "Support to avoid cyclic dependency and " +
                                    "TNP." + "\n")
                                i.AttachmentSupport = None # remove
            host.Subtractions = s
        elif Draft.getType(host) in ["SectionPlane"]:
            a = host.Objects
            for o in objectsList:
                if o in a:
                    a.remove(o)
            host.Objects = a
    else:
        for o in objectsList:
            if o.InList:
                h = o.InList[0]
                tp = Draft.getType(h)
                if tp in ["Floor","Building","Site","BuildingPart"]:
                    c = h.Group
                    if o in c:
                        c.remove(o)
                        h.Group = c
                        o.ViewObject.show()
                elif tp in ["Wall","Structure","Precast"]:
                    a = h.Additions
                    s = h.Subtractions
                    if o in a:
                        a.remove(o)
                        h.Additions = a
                        o.ViewObject.show()
                    elif o in s:
                        s.remove(o)
                        h.Subtractions = s
                        o.ViewObject.show()
                    elif o == s.Base:
                        s.Base = None
                        o.ViewObject.show()
                elif tp in ["SectionPlane"]:
                    a = h.Objects
                    if o in a:
                        a.remove(o)
                        h.Objects = a
            if hasattr(o, "Hosts") and Draft.getType(o) == "Window":
                o.Hosts = []

def makeComponent(baseobj=None,name=None,delete=False):
    '''makeComponent([baseobj],[name],[delete]): creates an undefined, non-parametric BIM
    component from the given base object'''
    if not FreeCAD.ActiveDocument:
        FreeCAD.Console.PrintError("No active document. Aborting\n")
        return
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","Component")
    obj.Label = name if name else translate("Arch","Component")
    ArchComponent.Component(obj)
    if FreeCAD.GuiUp:
        ArchComponent.ViewProviderComponent(obj.ViewObject)
    if baseobj:
        import Part
        if hasattr(baseobj,'Shape'):
            obj.Shape = baseobj.Shape
            obj.Placement = baseobj.Placement
            if delete:
                FreeCAD.ActiveDocument.removeObject(baseobj.Name)
            else:
                obj.Base = baseobj
                if FreeCAD.GuiUp:
                    baseobj.ViewObject.hide()
        elif isinstance(baseobj,Part.Shape):
            obj.Shape = baseobj
    Draft.select(obj)
    return obj

def cloneComponent(obj):
    '''cloneComponent(obj): Creates a clone of an object as an undefined component'''
    c = makeComponent()
    c.CloneOf = obj
    c.Placement = obj.Placement
    c.Label = obj.Label
    if hasattr(obj,"Material"):
        if obj.Material:
            c.Material = obj.Material
    if hasattr(obj,"IfcAttributes"):
        if obj.IfcAttributes:
            c.IfcAttributes = obj.IfcAttributes
    Draft.select(c)
    return c

def setAsSubcomponent(obj):
    '''Sets the given object properly to become a subcomponent (addition, subtraction)
    of an Arch component'''
    Draft.ungroup(obj)
    if params.get_param_arch("applyConstructionStyle"):
        if FreeCAD.GuiUp:
            color = getDefaultColor("Construction")
            if hasattr(obj.ViewObject,"LineColor"):
                obj.ViewObject.LineColor = color
            if hasattr(obj.ViewObject, "PointColor"):
                obj.ViewObject.PointColor = color
            if hasattr(obj.ViewObject,"ShapeColor"):
                obj.ViewObject.ShapeColor = color
            if hasattr(obj.ViewObject,"Transparency"):
                obj.ViewObject.Transparency = int(color[3]*100)
            obj.ViewObject.hide()

def copyProperties(obj1,obj2):
    '''copyProperties(obj1,obj2): Copies properties values from obj1 to obj2,
    when that property exists in both objects'''
    for prop in obj1.PropertiesList:
        if prop in obj2.PropertiesList:
            if not prop in ["Proxy","Shape"]:
                setattr(obj2,prop,getattr(obj1,prop))
    if obj1.ViewObject and obj2.ViewObject:
        for prop in obj1.ViewObject.PropertiesList:
            if prop in obj2.ViewObject.PropertiesList:
                if not prop in ["Proxy","Shape"]:
                    setattr(obj2.ViewObject,prop,getattr(obj1.ViewObject,prop))

def splitMesh(obj,mark=True):
    '''splitMesh(object,[mark]): splits the given mesh object into separated components.
    If mark is False, nothing else is done. If True (default), non-manifold components
    will be painted in red.'''
    if not obj.isDerivedFrom("Mesh::Feature"): return []
    basemesh = obj.Mesh
    comps = basemesh.getSeparateComponents()
    nlist = []
    if comps:
        basename = obj.Name
        FreeCAD.ActiveDocument.removeObject(basename)
        for c in comps:
            newobj = FreeCAD.ActiveDocument.addObject("Mesh::Feature",basename)
            newobj.Mesh = c
            if mark and (not(c.isSolid()) or c.hasNonManifolds()):
                newobj.ViewObject.ShapeColor = (1.0,0.0,0.0,1.0)
            nlist.append(newobj)
        return nlist
    return [obj]

def makeFace(wires,method=2,cleanup=False):
    '''makeFace(wires): makes a face from a list of wires, finding which ones are holes'''
    #print("makeFace: start:", wires)
    import Part

    if not isinstance(wires,list):
        if len(wires.Vertexes) < 3:
            raise
        return Part.Face(wires)
    elif len(wires) == 1:
        #import Draft;Draft.printShape(wires[0])
        if len(wires[0].Vertexes) < 3:
            raise
        return Part.Face(wires[0])

    wires = wires[:]

    #print("makeFace: inner wires found")
    ext = None
    max_length = 0
    # cleaning up rubbish in wires
    if cleanup:
        for i in range(len(wires)):
            wires[i] = DraftGeomUtils.removeInterVertices(wires[i])
        #print("makeFace: garbage removed")
    for w in wires:
        # we assume that the exterior boundary is that one with
        # the biggest bounding box
        if w.BoundBox.DiagonalLength > max_length:
            max_length = w.BoundBox.DiagonalLength
            ext = w
    #print("makeFace: exterior wire", ext)
    wires.remove(ext)

    if method == 1:
        # method 1: reverse inner wires
        # all interior wires mark a hole and must reverse
        # their orientation, otherwise Part.Face fails
        for w in wires:
            #print("makeFace: reversing", w)
            w.reverse()
            # make sure that the exterior wires comes as first in the list
        wires.insert(0, ext)
        #print("makeFace: done sorting", wires)
        if wires:
            return Part.Face(wires)
    else:
        # method 2: use the cut method
        mf = Part.Face(ext)
        #print("makeFace: external face:", mf)
        for w in wires:
            f = Part.Face(w)
            #print("makeFace: internal face:", f)
            mf = mf.cut(f)
        #print("makeFace: final face:", mf.Faces)
        return mf.Faces[0]

def closeHole(shape):
    '''closeHole(shape): closes a hole in an open shape'''
    import DraftGeomUtils
    import Part
    # creating an edges lookup table
    lut = {}
    for face in shape.Faces:
        for edge in face.Edges:
            hc = edge.hashCode()
            if hc in lut:
                lut[hc] = lut[hc] + 1
            else:
                lut[hc] = 1
    # filter out the edges shared by more than one face
    bound = []
    for e in shape.Edges:
        if lut[e.hashCode()] == 1:
            bound.append(e)
    bound = Part.__sortEdges__(bound)
    try:
        nface = Part.Face(Part.Wire(bound))
        shell = Part.makeShell(shape.Faces+[nface])
        solid = Part.Solid(shell)
    except Part.OCCError:
        raise
    else:
        return solid

def getCutVolume(cutplane,shapes,clip=False,depth=None):
    """getCutVolume(cutplane,shapes,[clip,depth]): returns a cut face and a cut volume
    from the given shapes and the given cutting plane. If clip is True, the cutvolume will
    also cut off everything outside the cutplane projection. If depth is non-zero, geometry
    further than this distance will be clipped off"""
    if not shapes:
        return None,None,None
    if not cutplane.Faces:
        return None,None,None
    import Part
    if not isinstance(shapes,list):
        shapes = [shapes]
    # building boundbox
    bb = shapes[0].BoundBox
    for sh in shapes[1:]:
        bb.add(sh.BoundBox)
    bb.enlarge(1)
    # building cutplane space
    um = vm = wm = 0
    try:
        if hasattr(cutplane,"Shape"):
            p = cutplane.Shape.copy().Faces[0]
        else:
            p = cutplane.copy().Faces[0]
    except Part.OCCError:
        FreeCAD.Console.PrintMessage(translate("Arch","Invalid cut plane")+"\n")
        return None,None,None
    ce = p.CenterOfMass
    ax = p.normalAt(0,0)
    prm_range = p.ParameterRange # (uMin, uMax, vMin, vMax)
    u = p.valueAt(prm_range[0], 0).sub(p.valueAt(prm_range[1], 0)).normalize()
    v = u.cross(ax)
    if not bb.isCutPlane(ce,ax):
        #FreeCAD.Console.PrintMessage(translate("Arch","No objects are cut by the plane)+"\n")
        return None,None,None
    else:
        corners = [FreeCAD.Vector(bb.XMin,bb.YMin,bb.ZMin),
                   FreeCAD.Vector(bb.XMin,bb.YMax,bb.ZMin),
                   FreeCAD.Vector(bb.XMax,bb.YMin,bb.ZMin),
                   FreeCAD.Vector(bb.XMax,bb.YMax,bb.ZMin),
                   FreeCAD.Vector(bb.XMin,bb.YMin,bb.ZMax),
                   FreeCAD.Vector(bb.XMin,bb.YMax,bb.ZMax),
                   FreeCAD.Vector(bb.XMax,bb.YMin,bb.ZMax),
                   FreeCAD.Vector(bb.XMax,bb.YMax,bb.ZMax)]
        for c in corners:
            dv = c.sub(ce)
            um1 = DraftVecUtils.project(dv,u).Length
            um = max(um,um1)
            vm1 = DraftVecUtils.project(dv,v).Length
            vm = max(vm,vm1)
            wm1 = DraftVecUtils.project(dv,ax).Length
            wm = max(wm,wm1)
        vu = DraftVecUtils.scaleTo(u,um)
        vui = vu.negative()
        vv = DraftVecUtils.scaleTo(v,vm)
        vvi = vv.negative()
        p1 = ce.add(vu.add(vvi))
        p2 = ce.add(vu.add(vv))
        p3 = ce.add(vui.add(vv))
        p4 = ce.add(vui.add(vvi))
        cutface = Part.makePolygon([p1,p2,p3,p4,p1])
        cutface = Part.Face(cutface)
        cutnormal = DraftVecUtils.scaleTo(ax,wm)
        cutvolume = cutface.extrude(cutnormal)
        cutnormal = cutnormal.negative()
        invcutvolume = cutface.extrude(cutnormal)
        if clip:
            extrudedplane = p.extrude(cutnormal)
            bordervolume = invcutvolume.cut(extrudedplane)
            cutvolume = cutvolume.fuse(bordervolume)
            cutvolume = cutvolume.removeSplitter()
            invcutvolume = extrudedplane
            cutface = p
        if depth:
            depthnormal = DraftVecUtils.scaleTo(cutnormal,depth)
            depthvolume = cutface.extrude(depthnormal)
            depthclipvolume = invcutvolume.cut(depthvolume)
            cutvolume = cutvolume.fuse(depthclipvolume)
            cutvolume = cutvolume.removeSplitter()
        return cutface,cutvolume,invcutvolume

def getShapeFromMesh(mesh,fast=True,tolerance=0.001,flat=False,cut=True):
    import Part
    import MeshPart
    import DraftGeomUtils
    if mesh.isSolid() and (mesh.countComponents() == 1) and fast:
        # use the best method
        faces = []
        for f in mesh.Facets:
            p=f.Points+[f.Points[0]]
            pts = []
            for pp in p:
                pts.append(FreeCAD.Vector(pp[0],pp[1],pp[2]))
            try:
                f = Part.Face(Part.makePolygon(pts))
            except Exception:
                print("getShapeFromMesh: error building face from polygon")
                #pass
            else:
                faces.append(f)
        shell = Part.makeShell(faces)
        try:
            solid = Part.Solid(shell)
        except Part.OCCError:
            print("getShapeFromMesh: error creating solid")
        else:
            try:
                solid = solid.removeSplitter()
            except Part.OCCError:
                print("getShapeFromMesh: error removing splitter")
                #pass
            return solid

    #if not mesh.isSolid():
    #    print "getShapeFromMesh: non-solid mesh, using slow method"
    faces = []
    segments = mesh.getPlanarSegments(tolerance)
    #print(len(segments))
    for i in segments:
        if len(i) > 0:
            wires = MeshPart.wireFromSegment(mesh, i)
            if wires:
                if flat:
                    nwires = []
                    for w in wires:
                        nwires.append(DraftGeomUtils.flattenWire(w))
                    wires = nwires
                try:
                    faces.append(makeFace(wires,method=int(cut)+1))
                except Exception:
                    return None
    try:
        se = Part.makeShell(faces)
        se = se.removeSplitter()
        if flat:
            return se
    except Part.OCCError:
        print("getShapeFromMesh: error removing splitter")
        try:
            cp = Part.makeCompound(faces)
        except Part.OCCError:
            print("getShapeFromMesh: error creating compound")
            return None
        else:
            return cp
    else:
        try:
            solid = Part.Solid(se)
        except Part.OCCError:
            print("getShapeFromMesh: error creating solid")
            return se
        else:
            if solid.isClosed():
                return solid
            else:
                return se

def projectToVector(shape,vector):
    '''projectToVector(shape,vector): projects the given shape on the given
    vector'''
    projpoints = []
    minl = 10000000000
    maxl = -10000000000
    for v in shape.Vertexes:
        p = DraftVecUtils.project(v.Point,vector)
        projpoints.append(p)
        l = p.Length
        if p.getAngle(vector) > 1:
            l = -l
        if l > maxl:
            maxl = l
        if l < minl:
            minl = l
    return DraftVecUtils.scaleTo(vector,maxl-minl)

def meshToShape(obj,mark=True,fast=True,tol=0.001,flat=False,cut=True):
    '''meshToShape(object,[mark,fast,tol,flat,cut]): turns a mesh into a shape, joining coplanar facets. If
    mark is True (default), non-solid objects will be marked in red. Fast uses a faster algorithm by
    building a shell from the facets then removing splitter, tol is the tolerance used when converting
    mesh segments to wires, flat will force the wires to be perfectly planar, to be sure they can be
    turned into faces, but this might leave gaps in the final shell. If cut is true, holes in faces are
    made by subtraction (default)'''

    name = obj.Name
    if "Mesh" in obj.PropertiesList:
        mesh = obj.Mesh
        #plac = obj.Placement
        solid = getShapeFromMesh(mesh,fast,tol,flat,cut)
        if solid:
            if solid.isClosed() and solid.isValid():
                FreeCAD.ActiveDocument.removeObject(name)
            newobj = FreeCAD.ActiveDocument.addObject("Part::Feature",name)
            newobj.Shape = solid
            #newobj.Placement = plac #the placement is already computed in the mesh
            if (not solid.isClosed()) or (not solid.isValid()):
                if mark:
                    newobj.ViewObject.ShapeColor = (1.0,0.0,0.0,1.0)
            return newobj
    return None

def removeCurves(shape,dae=False,tolerance=5):
    '''removeCurves(shape,dae,tolerance=5): replaces curved faces in a shape
    with faceted segments. If dae is True, DAE triangulation options are used'''
    import Mesh
    if dae:
        from importers import importDAE
        t = importDAE.triangulate(shape.cleaned())
    else:
        t = shape.cleaned().tessellate(tolerance)
    m = Mesh.Mesh(t)
    return getShapeFromMesh(m)

def removeShape(objs,mark=True):
    '''removeShape(objs,mark=True): takes an arch object (wall or structure) built on a cubic shape, and removes
    the inner shape, keeping its length, width and height as parameters. If mark is True, objects that cannot
    be processed by this function will become red.'''
    import DraftGeomUtils
    if not isinstance(objs,list):
        objs = [objs]
    for obj in objs:
        if DraftGeomUtils.isCubic(obj.Shape):
            dims = DraftGeomUtils.getCubicDimensions(obj.Shape)
            if dims:
                name = obj.Name
                tp = Draft.getType(obj)
                print(tp)
                if tp == "Structure":
                    FreeCAD.ActiveDocument.removeObject(name)
                    import ArchStructure
                    str = ArchStructure.makeStructure(length=dims[1],width=dims[2],height=dims[3],name=name)
                    str.Placement = dims[0]
                elif tp == "Wall":
                    FreeCAD.ActiveDocument.removeObject(name)
                    import ArchWall
                    length = dims[1]
                    width = dims[2]
                    v1 = Vector(length/2,0,0)
                    v2 = v1.negative()
                    v1 = dims[0].multVec(v1)
                    v2 = dims[0].multVec(v2)
                    line = Draft.makeLine(v1,v2)
                    ArchWall.makeWall(line,width=width,height=dims[3],name=name)
        else:
            if mark:
                obj.ViewObject.ShapeColor = (1.0,0.0,0.0,1.0)

def mergeCells(objectslist):
    '''mergeCells(objectslist): merges the objects in the given list
    into one. All objects must be of the same type and based on the Cell
    object (cells, floors, buildings, or sites).'''
    if not objectslist:
        return None
    if not isinstance(objectslist,list):
        return None
    if len(objectslist) < 2:
        return None
    typ = Draft.getType(objectslist[0])
    if not(typ in ["Cell","Floor","Building","Site"]):
        return None
    for o in objectslist:
        if Draft.getType(o) != typ:
            return None
    base = objectslist.pop(0)
    for o in objectslist:
        l = base.Components
        for c in o.Components:
            if not c in l:
                l.append(c)
        base.Components = l
        FreeCAD.ActiveDocument.removeObject(o.Name)
    FreeCAD.ActiveDocument.recompute()
    return base

def download(url,force=False):
    '''download(url,force=False): downloads a file from the given URL and saves it in the
    macro path. Returns the path to the saved file. If force is True, the file will be
    downloaded again evn if it already exists.'''
    try:
        from urllib.request import urlopen
    except ImportError:
        from urllib2 import urlopen
    import os
    name = url.split('/')[-1]
    macropath = FreeCAD.getUserMacroDir(True)
    filepath = os.path.join(macropath,name)
    if os.path.exists(filepath) and not(force):
        return filepath
    try:
        FreeCAD.Console.PrintMessage("downloading "+url+" ...\n")
        response = urlopen(url)
        s = response.read()
        f = open(filepath,'wb')
        f.write(s)
        f.close()
    except Exception:
        return None
    else:
        return filepath

def check(objectslist,includehidden=False):
    """check(objectslist,includehidden=False): checks if the given objects contain only solids"""
    objs = Draft.get_group_contents(objectslist)
    if not includehidden:
        objs = Draft.removeHidden(objs)
    bad = []
    for o in objs:
        if not hasattr(o,'Shape'):
            bad.append([o,"is not a Part-based object"])
        else:
            s = o.Shape
            if (not s.isClosed()) and (not (Draft.getType(o) == "Axis")):
                bad.append([o,translate("Arch","is not closed")])
            elif not s.isValid():
                bad.append([o,translate("Arch","is not valid")])
            elif (not s.Solids) and (not (Draft.getType(o) == "Axis")):
                bad.append([o,translate("Arch","doesn't contain any solid")])
            else:
                f = 0
                for sol in s.Solids:
                    f += len(sol.Faces)
                    if not sol.isClosed():
                        bad.append([o,translate("Arch","contains a non-closed solid")])
                if len(s.Faces) != f:
                    bad.append([o,translate("Arch","contains faces that are not part of any solid")])
    return bad

def getHost(obj,strict=True):
    """getHost(obj,[strict]): returns the host of the current object. If strict is true (default),
    the host can only be an object of a higher level than the given one, or in other words, if a wall
    is contained in another wall which is part of a floor, the floor is returned instead of the parent wall"""
    import Draft
    t = Draft.getType(obj)
    for par in obj.InList:
        if par.isDerivedFrom("Part::Feature") or par.isDerivedFrom("App::DocumentObjectGroup"):
            if strict:
                if Draft.getType(par) != t:
                    return par
                else:
                    return getHost(par,strict)
            else:
                return par
    return None

def pruneIncluded(objectslist,strict=False,silent=False):
    """pruneIncluded(objectslist,[strict]): removes from a list of Arch objects, those that are subcomponents of
    another shape-based object, leaving only the top-level shapes. If strict is True, the object
    is removed only if the parent is also part of the selection."""
    import Draft
    newlist = []
    for obj in objectslist:
        toplevel = True
        if obj.isDerivedFrom("Part::Feature"):
            if Draft.getType(obj) not in ["Window","Clone","Pipe","Rebar","Roof"]:
                for parent in obj.InList:
                    if not parent.isDerivedFrom("Part::Feature"):
                        pass
                    elif parent.isDerivedFrom("Part::Part2DObject"):
                        # don't consider 2D objects based on arch elements
                        pass
                    elif Draft.getType(parent) in [
                            "BezCurve", "BSpline", "Clone", "Facebinder", "Wire",
                            "Project", "Roof", "Site", "Space", "Window"
                        ]:
                        pass
                    elif parent.isDerivedFrom("PartDesign::FeatureBase"):
                        # don't consider a PartDesign_Clone that references obj
                        pass
                    elif parent.isDerivedFrom("PartDesign::Body") and obj == parent.BaseFeature:
                        # don't consider a PartDesign_Body with a PartDesign_Clone that references obj
                        pass
                    elif parent.isDerivedFrom("PartDesign::SubShapeBinder") or (hasattr(parent, "TypeId") and parent.TypeId == "PartDesign::ShapeBinder"):
                        # don't consider a PartDesign_SubShapeBinder or PartDesign_ShapeBinder referencing this object from another object
                        pass
                    elif hasattr(parent,"Host") and parent.Host == obj:
                        pass
                    elif hasattr(parent,"Hosts") and obj in parent.Hosts:
                        pass
                    elif hasattr(parent,"TypeId") and parent.TypeId == "Part::Mirroring":
                        pass
                    elif hasattr(parent,"CloneOf"):
                        if parent.CloneOf:
                            if parent.CloneOf.Name != obj.Name:
                                toplevel = False
                        else:
                            toplevel = False
                    else:
                        toplevel = False

                    if toplevel == False and strict:
                        if parent not in objectslist and parent not in newlist:
                            toplevel = True
        if toplevel:
            newlist.append(obj)
        elif not silent:
            FreeCAD.Console.PrintWarning("pruning "+obj.Label+"\n")
    return newlist

def getAllChildren(objectlist):
    "getAllChildren(objectlist): returns all the children of all the object sin the list"
    obs = []
    for o in objectlist:
        if not o in obs:
            obs.append(o)
        if o.OutList:
            l = getAllChildren(o.OutList)
            for c in l:
                if not c in obs:
                    obs.append(c)
    return obs


def survey(callback=False):
    """survey(): starts survey mode, where you can click edges and faces to get their lengths or area.
    Clicking on no object (on an empty area) resets the count."""
    if not callback:
        if hasattr(FreeCAD,"SurveyObserver"):
            for label in FreeCAD.SurveyObserver.labels:
                FreeCAD.ActiveDocument.removeObject(label)
            FreeCADGui.Selection.removeObserver(FreeCAD.SurveyObserver)
            del FreeCAD.SurveyObserver
            FreeCADGui.Control.closeDialog()
            if hasattr(FreeCAD,"SurveyDialog"):
                del FreeCAD.SurveyDialog
        else:
            FreeCAD.SurveyObserver = _SurveyObserver(callback=survey)
            FreeCADGui.Selection.addObserver(FreeCAD.SurveyObserver)
            FreeCAD.SurveyDialog = SurveyTaskPanel()
            FreeCADGui.Control.showDialog(FreeCAD.SurveyDialog)
    else:
        sel = FreeCADGui.Selection.getSelectionEx()
        if hasattr(FreeCAD,"SurveyObserver"):
            if not sel:
                if FreeCAD.SurveyObserver.labels:
                    for label in FreeCAD.SurveyObserver.labels:
                        FreeCAD.ActiveDocument.removeObject(label)
                    tl = FreeCAD.SurveyObserver.totalLength
                    ta = FreeCAD.SurveyObserver.totalArea
                    FreeCAD.SurveyObserver.labels = []
                    FreeCAD.SurveyObserver.selection = []
                    FreeCAD.SurveyObserver.totalLength = 0
                    FreeCAD.SurveyObserver.totalArea = 0
                    FreeCAD.SurveyObserver.totalVolume = 0
                    if not FreeCAD.SurveyObserver.cancellable:
                        FreeCAD.Console.PrintMessage("\n---- Reset ----\n\n")
                        FreeCAD.SurveyObserver.cancellable = True
                        if hasattr(FreeCAD,"SurveyDialog"):
                            FreeCAD.SurveyDialog.newline(tl,ta)
                    else:
                        FreeCADGui.Selection.removeObserver(FreeCAD.SurveyObserver)
                        del FreeCAD.SurveyObserver
                        FreeCADGui.Control.closeDialog()
                        if hasattr(FreeCAD,"SurveyDialog"):
                            del FreeCAD.SurveyDialog
            else:
                FreeCAD.SurveyObserver.cancellable = False
                basesel = FreeCAD.SurveyObserver.selection
                newsels = []
                for o in sel:
                    found = False
                    for eo in basesel:
                        if o.ObjectName == eo.ObjectName:
                            if o.SubElementNames == eo.SubElementNames:
                                found = True
                    if not found:
                        newsels.append(o)
                if newsels:
                    for o in newsels:
                        if hasattr(o.Object, 'Shape'):
                            n = o.Object.Label
                            showUnit = params.get_param_arch("surveyUnits")
                            t = ""
                            u = FreeCAD.Units.Quantity()
                            if not o.HasSubObjects:
                                # entire object
                                anno = FreeCAD.ActiveDocument.addObject("App::AnnotationLabel","surveyLabel")
                                if hasattr(o.Object.Shape,"CenterOfMass"):
                                    anno.BasePosition = o.Object.Shape.CenterOfMass
                                else:
                                    anno.BasePosition = o.Object.Shape.BoundBox.Center
                                FreeCAD.SurveyObserver.labels.append(anno.Name)
                                if o.Object.Shape.Solids:
                                    u = FreeCAD.Units.Quantity(o.Object.Shape.Volume,FreeCAD.Units.Volume)
                                    t = u.getUserPreferred()[0]
                                    t = t.replace("^3","³")
                                    anno.LabelText = "v " + t
                                    FreeCAD.Console.PrintMessage("Object: " + n + ", Element: Whole, Volume: " + t + "\n")
                                    FreeCAD.SurveyObserver.totalVolume += u.Value
                                elif o.Object.Shape.Faces:
                                    u = FreeCAD.Units.Quantity(o.Object.Shape.Area,FreeCAD.Units.Area)
                                    t = u.getUserPreferred()[0]
                                    t = t.replace("^2","²")
                                    anno.LabelText = "a " + t
                                    FreeCAD.Console.PrintMessage("Object: " + n + ", Element: Whole, Area: " + t + "\n")
                                    FreeCAD.SurveyObserver.totalArea += u.Value
                                    if hasattr(FreeCAD,"SurveyDialog"):
                                        FreeCAD.SurveyDialog.update(2,t)
                                else:
                                    u = FreeCAD.Units.Quantity(o.Object.Shape.Length,FreeCAD.Units.Length)
                                    t = u.getUserPreferred()[0]
                                    anno.LabelText = "l " + t
                                    FreeCAD.Console.PrintMessage("Object: " + n + ", Element: Whole, Length: " + t + "\n")
                                    FreeCAD.SurveyObserver.totalLength += u.Value
                                    if hasattr(FreeCAD,"SurveyDialog"):
                                        FreeCAD.SurveyDialog.update(1,t)
                                if FreeCAD.GuiUp and t:
                                    if showUnit:
                                        QtGui.QApplication.clipboard().setText(t)
                                    else:
                                        QtGui.QApplication.clipboard().setText(str(u.Value))
                            else:
                                # single element(s)
                                for el in o.SubElementNames:
                                    e = getattr(o.Object.Shape,el)
                                    anno = FreeCAD.ActiveDocument.addObject("App::AnnotationLabel","surveyLabel")
                                    if "Vertex" in el:
                                        anno.BasePosition = e.Point
                                    else:
                                        if hasattr(e,"CenterOfMass"):
                                            anno.BasePosition = e.CenterOfMass
                                        else:
                                            anno.BasePosition = e.BoundBox.Center
                                    FreeCAD.SurveyObserver.labels.append(anno.Name)
                                    if "Face" in el:
                                        u = FreeCAD.Units.Quantity(e.Area,FreeCAD.Units.Area)
                                        t = u.getUserPreferred()[0]
                                        t = t.replace("^2","²")
                                        anno.LabelText = "a " + t
                                        FreeCAD.Console.PrintMessage("Object: " + n + ", Element: " + el + ", Area: "+ t + "\n")
                                        FreeCAD.SurveyObserver.totalArea += u.Value
                                        if hasattr(FreeCAD,"SurveyDialog"):
                                            FreeCAD.SurveyDialog.update(2,t)
                                    elif "Edge" in el:
                                        u= FreeCAD.Units.Quantity(e.Length,FreeCAD.Units.Length)
                                        t = u.getUserPreferred()[0]
                                        anno.LabelText = "l " + t
                                        FreeCAD.Console.PrintMessage("Object: " + n + ", Element: " + el + ", Length: " + t + "\n")
                                        FreeCAD.SurveyObserver.totalLength += u.Value
                                        if hasattr(FreeCAD,"SurveyDialog"):
                                            FreeCAD.SurveyDialog.update(1,t)
                                    elif "Vertex" in el:
                                        u = FreeCAD.Units.Quantity(e.Z,FreeCAD.Units.Length)
                                        t = u.getUserPreferred()[0]
                                        anno.LabelText = "z " + t
                                        FreeCAD.Console.PrintMessage("Object: " + n + ", Element: " + el + ", Zcoord: " + t + "\n")
                                    if FreeCAD.GuiUp and t:
                                        if showUnit:
                                            QtGui.QApplication.clipboard().setText(t)
                                        else:
                                            QtGui.QApplication.clipboard().setText(str(u.Value))

                    FreeCAD.SurveyObserver.selection.extend(newsels)
            if hasattr(FreeCAD,"SurveyObserver"):
                if FreeCAD.SurveyObserver.totalLength or FreeCAD.SurveyObserver.totalArea or FreeCAD.SurveyObserver.totalVolume:
                    msg = " Total:"
                    if FreeCAD.SurveyObserver.totalLength:
                        u = FreeCAD.Units.Quantity(FreeCAD.SurveyObserver.totalLength,FreeCAD.Units.Length)
                        t = u.getUserPreferred()[0]
                        msg += " Length: " + t
                    if FreeCAD.SurveyObserver.totalArea:
                        u = FreeCAD.Units.Quantity(FreeCAD.SurveyObserver.totalArea,FreeCAD.Units.Area)
                        t = u.getUserPreferred()[0]
                        t = t.replace("^2","²")
                        msg += " Area: " + t
                    if FreeCAD.SurveyObserver.totalVolume:
                        u = FreeCAD.Units.Quantity(FreeCAD.SurveyObserver.totalVolume,FreeCAD.Units.Volume)
                        t = u.getUserPreferred()[0]
                        t = t.replace("^3","³")
                        msg += " Volume: " + t
                    FreeCAD.Console.PrintMessage(msg+"\n")

class _SurveyObserver:
    "an observer for the survey() function"
    def __init__(self,callback):
        self.callback = callback
        self.selection = []
        self.labels = []
        self.totalLength = 0
        self.totalArea = 0
        self.totalVolume = 0
        self.cancellable = False
        self.doubleclear = False

    def addSelection(self,document, object, element, position):
        self.doubleclear = False
        self.callback(True)

    def clearSelection(self,document):
        if not self.doubleclear:
            self.doubleclear = True
        else:
            self.callback(True)

class SurveyTaskPanel:
    "A task panel for the survey tool"

    def __init__(self):
        self.form = QtGui.QWidget()
        self.form.setWindowIcon(QtGui.QIcon(":/icons/Arch_Survey.svg"))
        layout = QtGui.QVBoxLayout(self.form)
        llayout = QtGui.QHBoxLayout()
        self.descr = QtGui.QLineEdit()
        llayout.addWidget(self.descr)
        self.addButton = QtGui.QPushButton()
        llayout.addWidget(self.addButton)
        layout.addLayout(llayout)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(3)
        layout.addWidget(self.tree)
        blayout = QtGui.QHBoxLayout()
        self.clearButton = QtGui.QPushButton()
        blayout.addWidget(self.clearButton)
        self.copyLength = QtGui.QPushButton()
        blayout.addWidget(self.copyLength)
        self.copyArea = QtGui.QPushButton()
        blayout.addWidget(self.copyArea)
        layout.addLayout(blayout)
        self.export = QtGui.QPushButton()
        layout.addWidget(self.export)
        QtCore.QObject.connect(self.addButton, QtCore.SIGNAL("clicked()"), self.setText)
        QtCore.QObject.connect(self.clearButton, QtCore.SIGNAL("clicked()"), self.clear)
        QtCore.QObject.connect(self.copyLength, QtCore.SIGNAL("clicked()"), self.clipLength)
        QtCore.QObject.connect(self.copyArea, QtCore.SIGNAL("clicked()"), self.clipArea)
        QtCore.QObject.connect(self.export, QtCore.SIGNAL("clicked()"), self.exportCSV)
        QtCore.QObject.connect(self.tree, QtCore.SIGNAL("itemClicked(QTreeWidgetItem*,int)"), self.setDescr)
        self.retranslateUi(self)
        item = QtGui.QTreeWidgetItem(self.tree)
        self.tree.setCurrentItem(item)

    def retranslateUi(self,dlg):
        self.form.setWindowTitle(QtGui.QApplication.translate("Arch", "Survey", None))
        self.addButton.setText(QtGui.QApplication.translate("Arch", "Set description", None))
        self.clearButton.setText(QtGui.QApplication.translate("Arch", "Clear", None))
        self.copyLength.setText(QtGui.QApplication.translate("Arch", "Copy Length", None))
        self.copyArea.setText(QtGui.QApplication.translate("Arch", "Copy Area", None))
        self.export.setText(QtGui.QApplication.translate("Arch", "Export CSV", None))
        self.tree.setHeaderLabels([QtGui.QApplication.translate("Arch", "Description", None),
                                   QtGui.QApplication.translate("Arch", "Length", None),
                                   QtGui.QApplication.translate("Arch", "Area", None)])

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.Close

    def reject(self):
        if hasattr(FreeCAD,"SurveyObserver"):
            for label in FreeCAD.SurveyObserver.labels:
                FreeCAD.ActiveDocument.removeObject(label)
            FreeCADGui.Selection.removeObserver(FreeCAD.SurveyObserver)
            del FreeCAD.SurveyObserver
        return True

    def clear(self):
        FreeCADGui.Selection.clearSelection()

    def clipLength(self):
        if hasattr(FreeCAD,"SurveyObserver"):
            u = FreeCAD.Units.Quantity(FreeCAD.SurveyObserver.totalLength,FreeCAD.Units.Length)
            t = u.getUserPreferred()[0]
            if params.get_param_arch("surveyUnits"):
                QtGui.QApplication.clipboard().setText(t)
            else:
                QtGui.QApplication.clipboard().setText(str(u.Value/u.getUserPreferred()[1]))

    def clipArea(self):
        if hasattr(FreeCAD,"SurveyObserver"):
            u = FreeCAD.Units.Quantity(FreeCAD.SurveyObserver.totalArea,FreeCAD.Units.Area)
            t = u.getUserPreferred()[0]
            t = t.replace("^2","²")
            if params.get_param_arch("surveyUnits"):
                QtGui.QApplication.clipboard().setText(t)
            else:
                QtGui.QApplication.clipboard().setText(str(u.Value/u.getUserPreferred()[1]))

    def newline(self,length=0,area=0):
        FreeCADGui.Selection.clearSelection()
        item = QtGui.QTreeWidgetItem(self.tree)
        if length or area:
            item.setText(0,QtGui.QApplication.translate("Arch", "Total", None))
            item.setToolTip(0,"total")
            f = QtGui.QFont()
            f.setBold(True)
            item.setFont(0,f)
            item.setFont(1,f)
            item.setFont(2,f)
        else:
            item.setText(0,self.descr.text())
            self.descr.setText("")
        self.tree.setCurrentItem(item)
        if length:
            u = FreeCAD.Units.Quantity(length,FreeCAD.Units.Length)
            t = u.getUserPreferred()[0]
            item.setText(1,t)
        if area:
            u = FreeCAD.Units.Quantity(area,FreeCAD.Units.Area)
            t = u.getUserPreferred()[0]
            t = t.replace(u"^2",u"²")
            item.setText(2,t)
        if length or area:
            item = QtGui.QTreeWidgetItem(self.tree)
            self.tree.setCurrentItem(item)

    def update(self,column,txt):
        item = QtGui.QTreeWidgetItem(self.tree)
        self.tree.setCurrentItem(item)
        item.setText(column,txt)

    def setDescr(self,item,col):
        self.descr.setText(item.text(0))

    def setText(self):
        item = self.tree.currentItem()
        if item:
            item.setText(0,self.descr.text())
            self.descr.setText("")

    def exportCSV(self):
        import csv
        rows = self.tree.topLevelItemCount()
        if rows:
            filename = QtGui.QFileDialog.getSaveFileName(QtGui.QApplication.activeWindow(), translate("Arch","Export CSV File"), None, "CSV file (*.csv)")
            if filename:
                with open(filename[0].encode("utf8"), "w") as csvfile:
                    csvfile = csv.writer(csvfile,delimiter="\t")
                    suml = 0
                    for i in range(rows):
                        item = self.tree.topLevelItem(i)
                        row = []
                        row.append(item.text(0))
                        if item.text(1):
                            u = FreeCAD.Units.Quantity(item.text(1))
                            if item.toolTip(0) == "total":
                                row.append("=SUM(B"+str(suml+1)+":B"+str(i)+")")
                            else:
                                row.append(u.Value/u.getUserPreferred()[1])
                            row.append(u.getUserPreferred()[2])
                        else:
                            row.extend(["",""])
                        if item.text(2):
                            t = item.text(2).replace(u"²",u"^2")
                            u = FreeCAD.Units.Quantity(t)
                            if item.toolTip(0) == "total":
                                row.append("=SUM(D"+str(suml+1)+":D"+str(i)+")")
                            else:
                                row.append(u.Value/u.getUserPreferred()[1])
                            row.append(u.getUserPreferred()[2])
                        else:
                            row.extend(["",""])
                        csvfile.writerow(row)
                        if item.toolTip(0) == "total":
                            suml = i+1
                print("successfully exported ",filename[0])


def toggleIfcBrepFlag(obj):
    """toggleIfcBrepFlag(obj): toggles the IFC brep flag of the given object, forcing it
    to be exported as brep geometry or not."""
    if not hasattr(obj,"IfcData"):
        FreeCAD.Console.PrintMessage(translate("Arch","Object doesn't have settable IFC attributes"))
    else:
        d = obj.IfcData
        if "FlagForceBrep" in d:
            if d["FlagForceBrep"] == "True":
                d["FlagForceBrep"] = "False"
                FreeCAD.Console.PrintMessage(translate("Arch","Disabling B-rep force flag of object")+" "+obj.Label+"\n")
            else:
                d["FlagForceBrep"] = "True"
                FreeCAD.Console.PrintMessage(translate("Arch","Enabling B-rep force flag of object")+" "+obj.Label+"\n")
        else:
            d["FlagForceBrep"] = "True"
            FreeCAD.Console.PrintMessage(translate("Arch","Enabling B-rep force flag of object")+" "+obj.Label+"\n")
        obj.IfcData = d


def makeCompoundFromSelected(objects=None):
    """makeCompoundFromSelected([objects]): Creates a new compound object from the given
    subobjects (faces, edges) or from the selection if objects is None"""
    import FreeCADGui
    import Part
    so = []
    if not objects:
        objects = FreeCADGui.Selection.getSelectionEx()
    if not isinstance(objects,list):
        objects = [objects]
    for o in objects:
        so.extend(o.SubObjects)
    if so:
        c = Part.makeCompound(so)
        Part.show(c)


def cleanArchSplitter(objects=None):
    """cleanArchSplitter([objects]): removes the splitters from the base shapes
    of the given Arch objects or selected Arch objects if objects is None"""
    import FreeCAD
    import FreeCADGui
    if not objects:
        objects = FreeCADGui.Selection.getSelection()
    if not isinstance(objects,list):
        objects = [objects]
    for obj in objects:
        if hasattr(obj,'Shape'):
            if hasattr(obj,"Base"):
                if obj.Base:
                    print("Attempting to clean splitters from ", obj.Label)
                    base = obj.Base.getLinkedObject()
                    if base.isDerivedFrom("Part::Feature"):
                        if not base.Shape.isNull():
                            base.Shape = base.Shape.removeSplitter()
    FreeCAD.ActiveDocument.recompute()


def rebuildArchShape(objects=None):
    """rebuildArchShape([objects]): takes the faces from the base shape of the given (or selected
    if objects is None) Arch objects, and tries to rebuild a valid solid from them."""
    import FreeCAD
    import Part
    if not objects and FreeCAD.GuiUp:
        objects = FreeCADGui.Selection.getSelection()
    if not isinstance(objects,list):
        objects = [objects]
    for obj in objects:
        success = False
        if hasattr(obj,'Shape'):
            if hasattr(obj,"Base"):
                if obj.Base:
                    try:
                        print("Attempting to rebuild ", obj.Label)
                        base = obj.Base.getLinkedObject()
                        if base.isDerivedFrom("Part::Feature"):
                            if not base.Shape.isNull():
                                faces = []
                                for f in base.Shape.Faces:
                                    f2 = Part.Face(f.Wires)
                                    #print("rebuilt face: isValid is ", f2.isValid())
                                    faces.append(f2)
                                if faces:
                                    shell = Part.Shell(faces)
                                    if shell:
                                        #print("rebuilt shell: isValid is ", shell.isValid())
                                        solid = Part.Solid(shell)
                                        if solid:
                                            if not solid.isValid():
                                                solid.sewShape()
                                                solid = Part.Solid(solid)
                                            #print("rebuilt solid: isValid is ",solid.isValid())
                                            if solid.isValid():
                                                base.Shape = solid
                                                success = True
                    except Exception:
                        pass
        if not success:
            print ("Failed to rebuild a valid solid for object ",obj.Name)
    FreeCAD.ActiveDocument.recompute()


def getExtrusionData(shape,sortmethod="area"):
    """If a shape has been extruded, returns the base face, and extrusion vector.

    Determines if a shape appears to have been extruded from some base face, and
    extruded at the normal from that base face. IE: it looks like a cuboid.
    https://en.wikipedia.org/wiki/Cuboid#Rectangular_cuboid

    If this is the case, returns what appears to be the base face, and the vector
    used to make that extrusion.

    The base face is determined based on the sortmethod parameter, which can either
    be:

    "area" = Of the faces with the smallest area, the one with the lowest z coordinate.
    "z" = The face with the lowest z coordinate.
    a 3D vector = the face which center is closest to the given 3D point

    Parameters
    ----------
    shape: <Part.Shape>
        Shape to examine.
    sortmethod: {"area", "z"}
        Which sorting algorithm to use to determine the base face.

    Returns
    -------
    Extrusion data: list
        Two item list containing the base face, and the vector used to create the
        extrusion. In that order.
    Failure: None
        Returns None if the object does not appear to be an extrusion.
    """

    if shape.isNull():
        return None
    if not shape.Solids:
        return None
    if len(shape.Faces) < 3:
        return None
    # build faces list with normals
    faces = []
    import Part
    for f in shape.Faces:
        try:
            faces.append([f,f.normalAt(0,0)])
        except Part.OCCError:
            return None
    # find opposite normals pairs
    pairs = []
    for i1, f1 in enumerate(faces):
        for i2, f2 in enumerate(faces):
            if f1[0].hashCode() != f2[0].hashCode():
                if round(f1[1].getAngle(f2[1]),4) == 3.1416:
                    pairs.append([i1,i2])
    if not pairs:
        return None
    valids = []
    for pair in pairs:
        hc = [faces[pair[0]][0].hashCode(),faces[pair[1]][0].hashCode()]
        # check if other normals are all at 90 degrees
        ok = True
        for f in faces:
            if f[0].hashCode() not in hc:
                if round(f[1].getAngle(faces[pair[0]][1]),4) != 1.5708:
                    ok = False
        if ok:
            # prefer the face with the lowest z
            if faces[pair[0]][0].CenterOfMass.z < faces[pair[1]][0].CenterOfMass.z:
                valids.append([faces[pair[0]][0],faces[pair[1]][0].CenterOfMass.sub(faces[pair[0]][0].CenterOfMass)])
            else:
                valids.append([faces[pair[1]][0],faces[pair[0]][0].CenterOfMass.sub(faces[pair[1]][0].CenterOfMass)])
    if valids:
        if sortmethod == "z":
            valids.sort(key=lambda v: v[0].CenterOfMass.z)
        elif sortmethod == "area":
            # sort by smallest area
            valids.sort(key=lambda v: v[0].Area)
        else:
            valids.sort(key=lambda v: (v[0].CenterOfMass.sub(sortmethod)).Length)
        return valids[0]
    return None

def printMessage( message ):
    FreeCAD.Console.PrintMessage( message )
    if FreeCAD.GuiUp :
        QtGui.QMessageBox.information( None , "" , message )

def printWarning( message ):
    FreeCAD.Console.PrintMessage( message )
    if FreeCAD.GuiUp :
        QtGui.QMessageBox.warning( None , "" , message )

def makeIfcSpreadsheet(archobj=None):
    ifc_container = None
    for obj in FreeCAD.ActiveDocument.Objects :
        if obj.Name == "IfcPropertiesContainer" :
            ifc_container = obj
    if not ifc_container :
        ifc_container = FreeCAD.ActiveDocument.addObject('App::DocumentObjectGroup','IfcPropertiesContainer')
    import Spreadsheet
    ifc_spreadsheet = FreeCAD.ActiveDocument.addObject('Spreadsheet::Sheet','IfcProperties')
    ifc_spreadsheet.set('A1', translate("Arch","Category"))
    ifc_spreadsheet.set('B1', translate("Arch","Key"))
    ifc_spreadsheet.set('C1', translate("Arch","Type"))
    ifc_spreadsheet.set('D1', translate("Arch","Value"))
    ifc_spreadsheet.set('E1', translate("Arch","Unit"))
    ifc_container.addObject(ifc_spreadsheet)
    if archobj :
        if hasattr(obj,"IfcProperties") :
            archobj.IfcProperties = ifc_spreadsheet
            return ifc_spreadsheet
        else :
            FreeCAD.Console.PrintWarning(translate("Arch", "The object doesn't have an IfcProperties attribute. Cancel spreadsheet creation for object:")+ ' ' + archobj.Label)
            FreeCAD.ActiveDocument.removeObject(ifc_spreadsheet)
    else :
        return ifc_spreadsheet
