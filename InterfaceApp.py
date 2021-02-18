
import os
import atexit
import subprocess
import sys

from abc import abstractmethod, ABCMeta

import ui

import Utils
from AppKernel import AppKernel
from SummaryInfo import SummaryInfo


class InterfaceApp:
    def __init__(self, app: AppKernel = None, _gisdb: str = None, _location: str = None, _mapset: str = None):
        if app:
            self.app = app
        else:
            self.app = AppKernel(gisdb=_gisdb, location=_location, mapset=_mapset)

        self.gidsb = _gisdb
        self.location = _location
        self.mapset = _mapset

        self.linkage_in_file = None
        self.linkage_out_folder = None
        self.node_file = None
        self.arc_file = None
        self.catchment_file = None
        self.gw_file = None
        self.ds_folder = None
        self.epsg_code = None
        self.catchment_field = None
        self.gw_field = None
        self.ds_field = None

        # with option [-g]
        self.make_grid = False
        self.gw_model_file = None
        self.linkage_in_folder = None
        self.z_rotation = None
        self.x_ll = None  # real world model coords (lower left)
        self.y_ll = None  # real world model coords (lower left)

        self.errors = []

    @abstractmethod
    def print_catchment_summary(self):
        pass

    @abstractmethod
    def print_gw_summary(self):
        pass

    @abstractmethod
    def print_ds_summary(self):
        pass

    @abstractmethod
    def print_river_summary(self):
        pass

    @abstractmethod
    def print_main_summary(self):
        pass

    def set_gw_model(self, gw_model: str):
        self.make_grid = True

        self.gw_model_file = gw_model

    def set_linkage_in_folder(self, linkage_in_folder):
        self.make_grid = True

        self.linkage_in_folder = linkage_in_folder

    def set_z_rotation(self, z_rotation):
        self.make_grid = True

        # get z-rotation gw model
        try:
            self.z_rotation = float(z_rotation.strip())
        except ValueError as e:
            self.errors.append('Groundwater model rotation [{}] is not valid. Set to [0.0]'.format(z_rotation))
            self.z_rotation = 0.0
        except AttributeError as e:
            self.errors.append('Groundwater model rotation is empty. Set to [0.0]'.format(z_rotation))
            self.z_rotation = 0.0

    def set_gw_model_coords_lower_left(self, coords_ll):
        self.make_grid = True

        if coords_ll is None:
            self.errors.append('Lower left corner coordinates are empty'.format(coords_ll))
            coords_ll = [None, None]
        else:
            lower_left_corner = [c.strip() for c in coords_ll.split(',')]
            try:
                if len(lower_left_corner) > 1:
                    coords_ll = [float(lower_left_corner[0]), float(lower_left_corner[1])]
                else:
                    self.errors.append(
                        'Lower left corner coordinates [({})] are not valid.'.format(coords_ll))
                    coords_ll = [None, None]
            except ValueError as e:
                self.errors.append(
                    'Lower left corner coordinates [({})] are not valid.'.format(coords_ll))
                coords_ll = [None, None]

        self.x_ll = coords_ll[0]
        self.y_ll = coords_ll[1]

    def check_errors(self):
        _err = False
        if self.errors:
            _err = True

        return _err

    @abstractmethod
    def print_errors(self):
        pass

    def set_gisdb(self, gisdb: str):
        self.gidsb = gisdb

    def set_location(self, _location: str):
        self.location = _location

    def set_mapset(self, _mapset: str):
        self.mapset = _mapset

    def set_required_paths(self, linkage_in_file: str, linkage_out_folder: str, node_file: str, arc_file: str):
        if linkage_in_file and linkage_out_folder and arc_file and node_file:
            # set in app
            self.app.set_linkage_in_file(file_path=linkage_in_file)
            self.app.set_linkage_out_file(folder_path=linkage_out_folder)
            self.app.set_arc_file(file_path=arc_file)
            self.app.set_node_file(file_path=node_file)

            _errors = self.app.check_input_paths(required=True, additional=False)
            if _errors:
                for _err in _errors:
                    self.errors.append(_err)
            else:
                # set in properties
                self.linkage_in_file = linkage_in_file
                self.linkage_out_folder = linkage_out_folder
                self.node_file = node_file
                self.arc_file = arc_file
        else:
            self.errors.append('linkage_in file is requerid') if not linkage_in_file else None
            self.errors.append('linkage_out folder is requerid') if not linkage_out_folder else None
            self.errors.append('node file is requerid') if not node_file else None
            self.errors.append('arc file is requerid') if not arc_file else None

    def set_additional_paths(self, catchment_file: str, gw_file: str, ds_folder: str):
        # set in app
        self.app.set_catchment_file(file_path=catchment_file, is_main_file=True) if catchment_file else None
        self.app.set_groundwater_file(file_path=gw_file, is_main_file=True) if gw_file else None
        self.app.set_demand_site_folder(folder_path=ds_folder) if ds_folder else None

        _errors = self.app.check_input_paths(required=False, additional=True)
        if _errors:
            for _err in _errors:
                self.errors.append(_err)
        else:
            # set in properties
            self.catchment_file = catchment_file
            self.gw_file = gw_file
            self.ds_folder = ds_folder

    def set_epsg_code(self, epsg_code: str):
        try:
            self.epsg_code = int(epsg_code)
        except ValueError as e:
            self.errors.append('EPSG code [{}] is wrong'.format(epsg_code))
            self.epsg_code = None
        except TypeError as e:
            self.errors.append('EPSG code is empty'.format(epsg_code))
            self.epsg_code = None

    def set_feature_fields(self, catchment_field: str, gw_field: str, ds_field: str):
        # set in app
        self.app.set_config_field(catchment_field=catchment_field, groundwater_field=gw_field,
                                  demand_site_field=ds_field)

        # set in properties
        self.catchment_field = catchment_field
        self.gw_field = gw_field
        self.ds_field = ds_field

    @abstractmethod
    def print_input_summary(self):
        pass

    @classmethod
    def get_model_info(cls, gw_model):
        # flopy change SpatialReference for Grid (StructuredGrid) and now always
        # use LOWER LEFT (it used [ml.sr.origin_loc] bedore)
        print_info = {
            'ORIGIN REFERENCE': 'LOWER LEFT CORNER (ll)',
            'PROJECTION': gw_model.modelgrid.proj4,
            'LOWER LEFT CORNER': '({}, {})'.format(str(gw_model.modelgrid.xoffset), str(gw_model.modelgrid.yoffset)),
            'ROTATION': str(gw_model.modelgrid.angrot) + " DEGREES",
            'ROWS': gw_model.modelgrid.nrow,
            'COLS': gw_model.modelgrid.ncol,
            'LAYERS': gw_model.modelgrid.nlay,
            'GRID TYPE': gw_model.modelgrid.grid_type,
        }
        print_info['GRID TYPE'] += ' X-REGULAR' if gw_model.modelgrid.is_regular_x else ' X-NOT-REGULAR'
        print_info['GRID TYPE'] += ' Y-REGULAR' if gw_model.modelgrid.is_regular_y else ' Y-NOT-REGULAR'

        return print_info

    @abstractmethod
    def print_groundwater_model_info(self, gw_model):
        pass

    def make_linkage_grid(self, linkage_file_name: str):
        import flopy

        gw_model_file = self.gw_model_file
        linkage_folder = self.linkage_in_folder
        epsg_code = self.epsg_code

        msg_str = 'Reading groundwater model [{}]'.format(gw_model_file)
        yield msg_str

        model_path = os.path.dirname(gw_model_file)
        model_file = os.path.basename(gw_model_file)

        linkage_file_path = os.path.join(linkage_folder, linkage_file_name)

        try:
            ml = flopy.modflow.Modflow.load(model_file, model_ws=model_path, exe_name='mf2005', verbose=False, check=True)

            # get groundwater model info
            self.print_groundwater_model_info(gw_model=ml)

            # update structured grid with x_ll_real, y_ll_real, rot_degrees_cw (origin param)
            if self.x_ll is not None and self.y_ll is not None:
                if self.z_rotation is not None:
                    ml.modelgrid.set_coord_info(xoff=self.x_ll, yoff=self.y_ll, angrot=self.z_rotation,
                                                epsg=self.epsg_code, merge_coord_info=True)
                else:
                    ml.modelgrid.set_coord_info(xoff=self.x_ll, yoff=self.y_ll, angrot=0.0,
                                                epsg=self.epsg_code, merge_coord_info=True)
                # save to shapefile
                # ml.dis.export(linkage_file_path, epsg=int(epsg_code))
                ml.modelgrid.write_shapefile(filename=linkage_file_path, epsg=self.epsg_code)

                # check if it exists new file
                if not os.path.isfile(linkage_file_path):
                    msg_error = 'Input linkage shapefile could not be created: [{}]'.format(linkage_file_path)
                    self.errors.append(msg_error)

                    yield msg_error
                else:
                    self.linkage_in_file = linkage_file_path

                    msg_info = 'Input linkage shapefile was created successfully: [{}]'.format(linkage_file_path)
                    yield msg_info
            else:
                msg_error = 'Input linkage shapefile could not be created: [{}]'.format(linkage_file_path)
                self.errors.append(msg_error)

                # yield msg_error
        except OSError as e:
            ml = None

    @abstractmethod
    def check_args(self):
        print()
        pass

    @abstractmethod
    def run(self):
        pass


