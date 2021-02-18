import difflib
import os
import random
import re
from subprocess import PIPE
import sqlite3

import ui
from grass.pygrass.modules import Module
from grass.pygrass.vector import Vector, VectorTopo
from grass.pygrass.vector.table import Columns

from decorator import main_task


def get_origin_from_map(map_name: str):
    """Get the real world model coords for lower left edge in a vector map.
    :return (x,y) coords for lower left edge
    """
    v = VectorTopo(map_name)
    v.open('r')

    box = v.bbox()
    x_ll = box.west
    y_ll = box.south
    v.close()

    return x_ll, y_ll


def set_origin_in_map(map_name: str, map_name_out: str, x_offset_ll: float, y_offset_ll: float, z_rotation: float,
                      verbose: bool = False, quiet: bool = True):
    """Set lower left edge in vector map. """

    err = False
    errors = []

    vtransform = Module('v.transform', run_=False, stdout_=PIPE, stderr_=PIPE, verbose=verbose, overwrite=True,
                        quiet=quiet)

    vtransform.inputs.input = map_name
    vtransform.outputs.output = map_name_out
    vtransform.inputs.xshift = x_offset_ll
    vtransform.inputs.yshift = y_offset_ll
    vtransform.inputs.zrotation = z_rotation

    # print(vtransform.get_bash())
    vtransform.run()

    return err, errors


def copy_from_location(mapname_in: str, mapname_out: str, location_in: str, mapset_in: str = 'PERMANENT',
                       verbose: bool = False, quiet: bool = True):
    err = False
    errors = []

    # import vector map in [map_path]
    vproj = Module('v.proj', run_=False, stdout_=PIPE, stderr_=PIPE, verbose=verbose, overwrite=True, quiet=quiet)

    vproj.inputs.input = mapname_in
    vproj.outputs.output = mapname_out

    vproj.inputs.location = location_in
    vproj.inputs.mapset = mapset_in

    # print(vproj.get_bash())
    vproj.run()
    # print(out_ogr.outputs["stdout"].value)

    return err, errors


def get_similarity_rate(a_words, b_words, min_rate=0.9):
    seq = difflib.SequenceMatcher(None, a_words, b_words)
    d = seq.quick_ratio()  # seq.ratio()

    return d >= min_rate


def check_paths_exist(files: list = None, folders: list = None):
    import os.path

    files = files if files else []
    folders = folders if folders else []

    # TODO: is it better to use os.path.exists?
    _result_files = []
    for file in files:
        if not os.path.isfile(file):
            msg_error = 'El archivo [{}] no existe.'.format(file)
            _result_files.append((False, msg_error))
        else:
            _result_files.append((True, None))

    _result_dirs = []
    for folder in folders:
        if not os.path.isdir(folder):
            msg_error = 'El directorio [{}] no existe.'.format(folder)
            _result_dirs.append((False, msg_error))
        else:
            _result_dirs.append((True, None))

    return _result_files, _result_dirs


def export_to_shapefile(map_name, output_path, file_name: str = 'linkage.shp', verbose: bool = False,
                        quiet: bool = True):
    err = False
    errors = []

    # import vector map in [map_path]
    out_ogr = Module('v.out.ogr', run_=False, stdout_=PIPE, stderr_=PIPE, verbose=verbose, overwrite=True, quiet=quiet)

    out_ogr.inputs.input = map_name
    out_ogr.inputs.type = ['auto']
    out_ogr.inputs.format = 'ESRI_Shapefile'

    out_ogr.outputs.output = '{}/{}'.format(output_path, file_name)
    out_ogr.flags.e = True

    # print(out_ogr.get_bash())
    out_ogr.run()
    # print(out_ogr.outputs["stdout"].value)

    return err, errors


# @main_task
def import_vector_map(map_path: str, output_name: str, verbose: bool = False, quiet: bool = True):
    err = False
    errors = []

    # import vector map in [map_path]
    in_ogr = Module('v.in.ogr', run_=False, stdout_=PIPE, stderr_=PIPE, verbose=verbose, overwrite=True, quiet=quiet)

    in_ogr.inputs.input = map_path
    in_ogr.outputs.output = output_name + '_tmp'
    in_ogr.flags.o = True

    # print(in_ogr.get_bash())
    in_ogr.run()
    # print(in_ogr.outputs["stdout"].value)

    # check if import works
    vector_map = Vector(output_name + '_tmp')
    if vector_map.exist():
        do_clean(map_name=output_name + '_tmp', map_new_name=output_name, tool=['rmarea', 'rmline', 'rmdac'],
                 threshold=['1', '0', '0'])
    else:
        err = True
        msg_error = 'El mapa [{}] en path=[{}] no pudo ser importado'.format(output_name, map_path)
        errors.append(msg_error)

    return err, errors


def do_clean(map_name=None, map_new_name=None, tool=['rmarea', 'rmline', 'rmdac'], threshold=['1', '0', '0'],
             verbose: bool = False, quiet: bool = True):
    vclean = Module('v.clean', run_=False, stdout_=PIPE, stderr_=PIPE, verbose=verbose, overwrite=True, quiet=quiet)

    vclean.inputs.input = map_name
    vclean.outputs.output = map_new_name

    vclean.inputs.tool = tool
    vclean.inputs.threshold = threshold

    # print(vclean.get_bash())
    vclean.run()
    # print(vclean.outputs["stdout"].value)

    return map_new_name


def make_values_to_db(vector_map, values_dict):
    db_path = vector_map.dblinks[0].database

    cols_sqlite = Columns(vector_map.name, sqlite3.connect(db_path))
    cols_in = cols_sqlite.items()
    col_key = cols_sqlite.key

    col_values = []
    col_keys = []
    for col in [c for c in cols_in if c[0] != col_key]:
        key_column, key_type = col

        col_values.append(values_dict[key_column] if key_column in values_dict else '')
        col_keys.append(key_column)

    # if __debug:
    #     print('VALUES to DB: ================================================================')
    #     print ('\n'.join(['   [{}] = {}'.format(c, v) for c, v in zip(col_keys, col_values)]))
    #     print('VALUES to DB: ----------------------------------------------------------------')

    return col_keys, col_values


# @main_task
def check_basic_columns(map_name, columns: list, needed: list):
    _err, _errors = False, []

    vector_map = VectorTopo(map_name)
    vector_map.open('r')

    db_path = vector_map.dblinks[0].database
    cols_sqlite = Columns(vector_map.name, sqlite3.connect(db_path))
    cols_in = cols_sqlite.items()

    cols = [c[0] for c in cols_in]
    for ind, c_check in enumerate(columns):
        if c_check not in cols and needed[ind]:
            _err = True
            msg_error = 'El mapa [{}] no tiene la columna necesaria: [{}].'.format(map_name, c_check)
            _errors.append(msg_error)
        elif c_check not in cols and not needed[ind]:
            _err = True
            msg_warn = 'El mapa [{}] no tiene la columna [{}] (se ingorará su valor durante el proceso)'.format(
                map_name, c_check)
            _errors.append(msg_warn)

    vector_map.close()

    return _err, _errors


def print_catchment_map(cells, element_set):
    tokens = ['+', '-', '*', '#', '0', '°']

    max_row = max([cell.row for cell in cells])  # 88
    max_col = max([cell.col for cell in cells])  # 67

    catchs_tokens = {}
    i = 0
    for c in element_set:
        if not str(c).isnumeric():
            catchs_tokens[c] = tokens[i]
            i += 1

    basic_str = "".join([" " for i in range(max_col)])
    rows = {}
    for cell in cells:
        row = cell.row
        col = cell.col
        catchment = cell.catchment

        if row in rows:
            s = rows[row][:col] + catchs_tokens[catchment] + rows[row][col + 1:]
        else:
            rows[row] = basic_str
            s = rows[row][:col] + catchs_tokens[catchment] + rows[row][col + 1:]
        rows[row] = s

    for row in rows:
        print(rows[row])


def create_table_attributes(vector_map_name, columns_str, layer=1, key='cat', verbose: bool = False,
                            quiet: bool = True):
    # add columns to vector map
    addtable = Module('v.db.addtable', run_=False, stdout_=PIPE, stderr_=PIPE, verbose=verbose, quiet=quiet)
    addtable.inputs.map = vector_map_name
    addtable.inputs.table = vector_map_name
    addtable.inputs.layer = layer
    # addtable.inputs.key = key
    addtable.inputs.columns = columns_str

    # print(addtable.get_bash())
    addtable.run()
    # print(addtable.outputs["stdout"].value)
    # print(addtable.outputs["stderr"].value)

    # for security, rebuild topology
    vbuild = Module('v.build', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)
    vbuild.inputs.map = vector_map_name
    vbuild.inputs.option = 'build'

    # print(vbuild.get_bash())
    vbuild.run()
    # print(vbuild.outputs["stdout"].value)
    # print(vbuild.outputs["stderr"].value)


def generate_word(length: int = 5, prefix: str = 'mapset_'):
    _signs = "abcdefghijklmnopqrstuvwxyz1234567890"

    word = ""
    for i in range(length):
        word += random.choice(_signs)

    return prefix + word


def show_title(msg_title, ch: str = '-', ch_len: int = 100, title_color=ui.green):
    count_str = ch_len - len(msg_title) if ch_len > len(msg_title) else 0
    print()
    print(ch * (ch_len + 2))
    ch = ' '
    ui.info_section(ui.bold, title_color, msg_title, ui.faint, ui.lightgray, ch * count_str)


def extract_map_with_condition(map_name, output_name, col_query: str, val_query: str, op_query: str = '=',
                               geo_check: str = 'point', verbose: bool = False, quiet: bool = True):
    _err, _errors = False, []

    extract = Module('v.extract', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)
    extract.inputs.input = map_name
    extract.outputs.output = output_name

    extract.inputs.where = "{}{}\'{}\'".format(col_query, op_query, val_query)
    extract.inputs.type = ['point', 'line', 'boundary', 'centroid', 'area']
    # print(extract.get_bash())
    extract.run()

    # check if it was created
    vector_map = VectorTopo(output_name)
    vector_map.open('rw')
    if not vector_map.exist() or vector_map.num_primitive_of(geo_check) == 0:  # extract works
        _err = True
        msg_warn = 'No se ha podido extraer del mapa [{}] con la condicion: [{} {} {}]'.format(map_name, col_query,
                                                                                               op_query, val_query)
        _errors.append(msg_warn)
    vector_map.close()

    return _err, _errors


def get_map_name_standard(f_path: str):
    f_path = os.path.basename(f_path)
    f_path = f_path.replace('.', '_')
    f_path = f_path.replace(',', '_')
    f_path = f_path.replace('-', '_')
    name = os.path.splitext(f_path)[0][0:30].lower()

    first_letter_patter = '[a-zA-Z]'
    if re.match(first_letter_patter, name[0]):
        return name
    else:
        return 'm' + name


def check_file_extension(file_path: str, ftype: str = 'shp'):
    file_name = os.path.splitext(file_path)[1].lower()
    if file_name.endswith('.{}'.format(ftype)):
        return True
    else:
        return False


def get_file_names(folder_path, ftype: str = 'shp') -> list:
    from os import listdir
    from os.path import isfile, join

    files = [join(folder_path, f) for f in listdir(folder_path) if isfile(join(folder_path, f))]
    files = [f for f in files if f.endswith('.{}'.format(ftype))] if ftype else files

    return files


def insert_ui(text: str, pattern: str = r"\[([A-Za-z0-9_/ .']+)\]", highlight_color=ui.red):
    effect_ini = [ui.bold, highlight_color]
    effect_fin = [ui.faint, ui.white]

    m = re.search(pattern, text)

    if m:
        subtext_ini = text[:m.start()].strip()
        subtext_inter = m.group(1).strip()
        subtext_fin = text[m.end():].strip()

        text_end = insert_ui(subtext_fin, pattern)

        ret = [subtext_ini, *effect_ini, subtext_inter, *effect_fin, *text_end]
        return ret
    else:
        return [text]
