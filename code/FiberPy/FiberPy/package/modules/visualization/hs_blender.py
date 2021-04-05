# -*- coding: utf-8 -*-
"""
Created on Fri Apr  2 22:22:51 2021

@author: ken
"""

# Blender objects
import bpy
import bmesh

import math

import numpy as np

# Half-sarcomere
import half_sarcomere as hs

class hs_blender():
    """ Class for a half-sarcomere in blender """

    def __init__(self, hs, frame, template, blender):

        # Create local copies
        self.hs = hs
        self.frame = frame
        self.template = template
        self.blender = blender

        # Set up yz_scaling
        self.yz_scaling = template['lattice']['inter_thick_nm']

        # Set up
        self.setup_blender_script()
        self.setup_render_engine()

        # Create obj dictionary
        self.b_obj = dict()

        # Create materials
        self.materials = dict()
        self.create_materials()

        # self.create_lists_and_collection()

        # Create a dictionary to hold blender primitives
        self.hs_b = dict()
        self.hs_b['primitives'] = dict()

        # Create the primitives
        self.create_primitive_m_crown()
        self.create_primitive_m_stub()
        self.create_primitive_m_cat()
        self.create_primitive_a_node()
        self.create_primitive_a_bs()

        # Create thick filaments
        for i, thick_fil in enumerate(self.hs.thick_fil):
            self.create_thick_filament(i)

        # Create thin filaments
        for i, thin_fil in enumerate(self.hs.thin_fil):
            self.create_thin_filament(i)

        # Create cross-bridges
        self.create_cross_bridges()

        # Create a camera
        self.create_camera()

        # Create lights
        self.create_lights()

        # # Link everything
        # self.link_all_objects()
        
        # print(list(bpy.data.objects))

        # Render
        self.render_screenshot()

    def setup_blender_script(self):
        """Adds boilerplate blender scripting instructions."""
        # Set mode to object mode since we have to do most of the operations there.

        if bpy.context.active_object != None and \
                bpy.context.active_object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Delete objects if they currently exist.
        if bpy.data.objects != []:
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()
  
        # Set the viewport background color to white.
        bpy.context.preferences.themes['Default']. \
            view_3d.space.gradients.high_gradient.hsv = (0.0, 0.0, 1.0)
        bpy.context.scene.world.use_nodes = False
        bpy.context.scene.world.color = (1, 1, 1)

    def setup_render_engine(self):
        """Sets up the render engine that we want to use."""
        # Setting the render samples to 8 instead of 64 to cut render time.
        # Note: I don't think this affects much since the objects aren't very reflective.
        # bpy.context.scene.eevee.taa_render_samples = 8

        if self.blender["render_quality"] == "high":
            bpy.context.scene.render.engine = 'CYCLES'
        elif self.blender["render_quality"] == "medium":
            # Opting for Blender's workbench render engine because it does a good job and it's fast.
            bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
            bpy.context.scene.display.shading.light = 'STUDIO'
            bpy.context.scene.view_settings.view_transform = 'Filmic'
            bpy.context.scene.display.shading.show_object_outline = True
            bpy.context.scene.view_settings.exposure = 1.5
            bpy.context.scene.view_settings.gamma = 1.1
            bpy.context.scene.display.shading.show_specular_highlight = True
            bpy.context.scene.display.shading.shadow_intensity = 0.1

    def create_camera(self):
        """ Creates a camera """

        loc = (self.frame['camera']['location']['x'],
               self.frame['camera']['location']['y'],
               self.frame['camera']['location']['z'])

        rot = (self.frame['camera']['rotation']['x'] * np.pi/180,
               self.frame['camera']['rotation']['y'] * np.pi/180,
               self.frame['camera']['rotation']['z'] * np.pi/180)

        bpy.ops.object.camera_add(
            enter_editmode=False,
            align='VIEW',
            location=loc,
            rotation=rot)
        bpy.context.object.data.lens = 35

        bpy.context.scene.camera = bpy.context.object

    def create_lights(self):
        """ Create lights around the half-sarcomere """
        print("lights")

    def create_lists_and_collection(self):
        """ Lists everything together """

        thick = bpy.data.collections.new(name='Thick collection')
        bpy.context.scene.collection.children.link(thick)

        for i, thick_fil in enumerate(self.hs.thick_fil):
            thick_id = ('m_%i' % i)
            self.b_obj[thick_id] = []
            col = bpy.data.collections.new(thick_id)
            thick.children.link(col)

        # Create the colletion for the primitives
        prim = bpy.data.collections.new(name='Primitives')
        bpy.context.scene.collection.children.link(prim)

    def change_object_collection(self, obj, new_collection):
        """ Links obj to new_collection and unlinks obj from current collection.
            Note: It's important to do this after you've finished modifying the primitive how you want since
            this invalidates any bpy.opys.object calls on the object (I think).
            """
        new_collection.objects.link(obj)
        obj.users_collection[0].objects.unlink(obj)

        # I have to deselect the object for some reason?
        obj.select_set(False)

    def link_all_objects(self):
        """Links all objects in `obj_lists` to the current collection
  
        Note: Collection is a Blender term and is how they manage large collections of objects 
            "efficiently."
                """
        # for key, o_list in self.b_obj.items():
        #     link = bpy.data.collections[key].objects.link
        #     for o in o_list:
        #         link(o)

    def render_screenshot(self):
        """Renders a screen capture of the current geometry."""

        bpy.context.scene.render.filepath = self.frame['image_file']
        bpy.context.scene.frame_set(1)
        bpy.ops.render.render(write_still=True)
        return

    def create_materials(self):
        """ Creates materials """

        mat = bpy.data.materials.new(name = "m_crown")
        mat.diffuse_color = self.template['thick_filament']['crown']['color']
        self.materials['m_crown'] = mat

        mat = bpy.data.materials.new(name = "a_node")
        mat.diffuse_color = self.template['thin_filament']['node']['color']
        self.materials['a_node'] = mat

    def create_thick_filament(self, thick_id):
        """ Creates thick_fil[id] """

        # Find the thick fil
        thick_f = self.hs.thick_fil[thick_id]

        # Loop through the nodes
        crown_indices = np.arange(0, thick_f.m_no_of_cbs,
                                  thick_f.m_cbs_per_node)
        for i, ind in enumerate(crown_indices):
            # crown = self.create_primitive_m_crown()
            crown = self.hs_b['primitives']['m_crown'].copy()
            crown.name = ('m_crown_%i_%i' % (thick_id, i))
            crown.location.x = thick_f.cb_x[ind]
            crown.location.y = self.yz_scaling * thick_f.m_y
            crown.location.z = self.yz_scaling * thick_f.m_z
            bpy.context.collection.objects.link(crown)

        # Loop through the cbs
        cb_indices = np.arange(0, thick_f.m_no_of_cbs)
        for i, ind in enumerate(cb_indices):
            stub = self.hs_b['primitives']['m_stub'].copy()
            stub.name = ('m_stub_%i_%i' % (thick_id, i))
            stub.location.x = thick_f.cb_x[ind]
            stub.location.y = self.yz_scaling * thick_f.m_y + \
                (self.template['thick_filament']['crown']['radius'] +
                     self.template['thick_filament']['myosin']['stub_height'] / 2.0) * \
                    np.sin(np.pi * thick_f.cb_angle[ind] / 180.0)
            stub.location.z = self.yz_scaling * thick_f.m_z + \
                (self.template['thick_filament']['crown']['radius'] +
                     self.template['thick_filament']['myosin']['stub_height'] / 2.0) * \
                    np.cos(np.pi * thick_f.cb_angle[ind] / 180.0)
            stub.rotation_euler.x = -(np.pi * thick_f.cb_angle[ind] / 180.0)
            bpy.context.collection.objects.link(stub)

        bpy.context.view_layer.update()

    def create_thin_filament(self, thin_id):
        """ Creates thin_fil[id] """
        
        # Set the thin file
        thin_f = self.hs.thin_fil[thin_id]

        # Loop throught the nodes
        node_indices = np.arange(0, thin_f.a_no_of_bs,
                                 thin_f.a_bs_per_node)
        for i, ind in enumerate(node_indices):
            node = self.hs_b['primitives']['a_node'].copy()
            node.name = ('a_node_%i_%i' % (thin_id, i))
            node.location.x = thin_f.bs_x[ind]
            node.location.y = self.yz_scaling * thin_f.a_y
            node.location.z = self.yz_scaling * thin_f.a_z
            bpy.context.collection.objects.link(node)

        # Loop through the bs
        bs_indices = np.arange(0, thin_f.a_no_of_bs)
        for i, ind in enumerate(bs_indices):
            bs = self.hs_b['primitives']['a_bs'].copy()
            bs.name = ('a_bs_%i_%i' % (thin_id, i))
            bs.location.x = thin_f.bs_x[ind]
            bs.location.y = self.yz_scaling * thin_f.a_y + \
                self.template['thin_filament']['node']['radius'] * \
                    np.sin(np.pi * thin_f.bs_angle[ind] / 180.0)
            bs.location.z = self.yz_scaling * thin_f.a_z + \
                self.template['thin_filament']['node']['radius'] * \
                    np.cos(np.pi * thin_f.bs_angle[ind] / 180.0)
            bs.rotation_euler.x = -(np.pi * thin_f.bs_angle[ind] / 180.0)
            bpy.context.collection.objects.link(bs)

        bpy.context.view_layer.update()

    def create_cross_bridges(self):
        """ Draws cross-bridges """

        # Loop through myosin heads
        for thick_i, thick_f in enumerate(self.hs.thick_fil):
            print(thick_i)
            if (thick_i>0):
                break
            
            for cb_i in np.arange(0, thick_f.m_no_of_cbs):
                # Get the myosin end of the cb
                stub_x = thick_f.cb_x[cb_i]
                stub_y = self.yz_scaling * thick_f.m_y + \
                    (self.template['thick_filament']['crown']['radius'] + \
                     self.template['thick_filament']['myosin']['stub_height']) * \
                        np.sin(np.pi * thick_f.cb_angle[cb_i] / 180.0)
                stub_z = self.yz_scaling * thick_f.m_z + \
                    (self.template['thick_filament']['crown']['radius'] + \
                     self.template['thick_filament']['myosin']['stub_height']) * \
                        np.cos(np.pi * thick_f.cb_angle[cb_i] / 180.0)

                if (thick_f.cb_bound_to_a_f[cb_i] >= 0):
                    # Head is bound
                    # Find the cb end of the link
                    # Find the bs end of the link
                    thin_f = self.hs.thin_fil[thick_f.cb_bound_to_a_f[cb_i]]
                    thin_bs = thick_f.cb_bound_to_a_n[cb_i]
                    distal_x = thin_f.bs_x[thin_bs]
                    distal_y = self.yz_scaling * thin_f.a_y + \
                        (self.template['thin_filament']['node']['radius'] + \
                         self.template['thin_filament']['bs']['depth']) * \
                            np.sin(np.pi * thin_f.bs_angle[thin_bs] / 180.0)
                    distal_z = self.yz_scaling * thin_f.a_z + \
                        (self.template['thin_filament']['node']['radius'] + \
                         self.template['thin_filament']['bs']['depth']) * \
                            np.cos(np.pi * thin_f.bs_angle[thin_bs] / 180.0)
                            
                elif (any(self.template['srx_states']==thick_f.cb_state[cb_i])):
                    # It's SRX
                    distal_x = stub_x + self.template['thick_filament']['myosin']['link_height']
                    distal_y = stub_y
                    distal_z = stub_z
                else:
                    # It's DRX
                    distal_x = stub_x
                    distal_y = stub_y + \
                        self.template['thick_filament']['myosin']['link_height'] * \
                            np.sin(np.pi * thick_f.cb_angle[cb_i] / 180.0)
                    distal_z = stub_z + \
                        self.template['thick_filament']['myosin']['link_height'] * \
                            np.cos(np.pi * thick_f.cb_angle[cb_i] / 180.0)

                # Draw link
                self.cylinder_between(stub_x, stub_y, stub_z,
                                      distal_x, distal_y, distal_z,
                                      self.template['thick_filament']['myosin']['link_radius'])

    def cylinder_between(self, x1, y1, z1, x2, y2, z2, r):
        """ Draws a cylinder between two points """

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1    
        dist = np.sqrt(dx**2 + dy**2 + dz**2)

        bpy.ops.mesh.primitive_cylinder_add(
            radius = r, 
            depth = dist,
            location = (dx/2 + x1, dy/2 + y1, dz/2 + z1),
            vertices = 4
            ) 

        phi = math.atan2(dy, dx) 
        theta = math.acos(dz/dist) 

        bpy.context.object.rotation_euler[1] = theta 
        bpy.context.object.rotation_euler[2] = phi 

    def create_primitive_m_crown(self):
        """ Creates an m_crown """

        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.template['thick_filament']['crown']['radius'],
            depth=self.template['thick_filament']['crown']['depth'],
            enter_editmode=False,
            location=(0, 0, 0),
            vertices=self.template['thick_filament']['crown']['vertices'],
            rotation=(0, np.pi/2, 0))

        m_crown = bpy.context.object
        mesh = m_crown.data
        mesh.materials.append(self.materials['m_crown'])

        self.hs_b['primitives']['m_crown'] = m_crown

    def create_primitive_m_stub(self):
        """ Creates an m_stub """

        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.template['thick_filament']['myosin']['stub_radius'],
            depth=self.template['thick_filament']['myosin']['stub_height'],
            enter_editmode=False,
            location=(0,0,0),
            vertices=self.template['thick_filament']['myosin']['stub_vertices'],
            rotation=(0,0,0))

        m_stub = bpy.context.object

        self.hs_b['primitives']['m_stub'] = m_stub

    def create_primitive_m_cat(self):
        """ Creates an m_cat_domain, where myosin binds to actin """

        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.template['thick_filament']['myosin']['cat_radius'],
            depth=self.template['thick_filament']['myosin']['cat_height'],
            enter_editmode=False,
            location=(0,0,0),
            vertices=self.template['thick_filament']['myosin']['cat_vertices'],
            rotation=(0,0,0))

        m_cat = bpy.context.object

        self.hs_b['primitives']['m_cat'] = m_cat

    def create_primitive_a_node(self):
        """ Creates an a_node """

        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.template['thin_filament']['node']['radius'],
            depth=self.template['thin_filament']['node']['depth'],
            enter_editmode=False,
            location=(0, 0, 0),
            vertices=self.template['thin_filament']['node']['vertices'],
            rotation=(0, np.pi/2, 0))

        a_node = bpy.context.object
        mesh = a_node.data
        mesh.materials.append(self.materials['a_node'])

        self.hs_b['primitives']['a_node'] = a_node

    def create_primitive_a_bs(self):
        """ Creates an a_bs"""

        bpy.ops.mesh.primitive_cylinder_add(
            radius=self.template['thin_filament']['bs']['radius'],
            depth=self.template['thin_filament']['bs']['depth'],
            enter_editmode=False,
            location=(0, 0, 0),
            vertices=self.template['thin_filament']['bs']['vertices'],
            rotation=(0, 0, 0))

        a_bs = bpy.context.object
        # mesh = a_bs.data
        # mesh.materials.append(self.materials['a_node'])

        self.hs_b['primitives']['a_bs'] = a_bs


    def return_all_filament_y_coords(self):
        """Returns a list of all filament y coordinates"""

        m_ys = [thick_obj.m_y for thick_obj in self.hs.thick_fil]
        a_ys = [thin_obj.a_y for thin_obj in self.hs.fhin_fil]

        return m_ys + a_ys

    def return_all_filament_z_coords(self):
        """Returns a list of all filament z coordinates"""

        m_zs = [thick_obj.m_z for thick_obj in self.hs.thick_fil]
        a_zs = [thin_obj.a_z for thin_obj in self.hs.thin.fil]

        return m_zs + a_zs

    def find_bounding_box_yz_positions(self):
        """Returns min/max yz positions of the bounding box of the geometry."""

        filament_y_positions = self.return_all_filament_y_coords()
        filament_z_positions = self.return_all_filament_z_coords()
        min_y = np.min(filament_y_positions)
        max_y = np.max(filament_y_positions)
        min_z = np.min(filament_z_positions)
        max_z = np.max(filament_z_positions)

        return ((min_y, max_y), (min_z, max_z))
