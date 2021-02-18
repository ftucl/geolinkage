from functools import wraps
import time

import ui

# make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type)
import Utils

msg_config = {
    'import_vector_map': 'Importando archivo [{map_path}] con nombre [{output_name}]',
    'setup_arcs': 'Leyendo geometrías de Esquema WEAP',
    '_inter_map_with_linkage': 'Intersectando mapa [{map_name}] con linkage',
    'get_catchments_from_map': 'Validando cuencas encontradas en esquema WEAP con archivo de cuencas',
    'get_gws_from_map': 'Validando acuíferos encontrados en esquema WEAP con archivo de acuíferos',
    # 'make_grid_cell': 'Procesando intersección con linkage',
    'make_cell_data_by_main_map': 'Procesando [{inter_map_geo_type}] de interseccion del mapa primario [{map_name}] con linkage',
    'make_cell_data_by_secondary_maps': 'Procesando [{inter_map_geo_type}] de interseccion del mapa secundario [{map_name}] con linkage',
    'make_segment_map': 'Calculando y almacenando divisiones en ríos',
    'init_linkage_file': 'Formateando estructura de archivo linkage',
    'mark_linkage_active': 'Guardando datos en archivo linkage',
    'export_to_shapefile': 'Exportando linkage a [{output_path}]',
    'check_basic_columns': 'Validando columnas necesarias para [{map_name}]: {columns}',
    'check_names_with_geo': 'Validando mapas con geometrías de nodos y arcos',
    'check_names_between_maps': 'Validando nombres de geometrias entre mapas',
    'get_ds_map_from_node_map': 'Generando mapa principal a partir de mapa de nodos',
    '_read_well_files': 'Leyendo el archivo [{well_path}] para identificar los pozos del mapa de Nodos.'
}


class TimerSummary:
    config_summary = {
        'CatchmentProcess.run': {
            'scope': 'catchment',
        },
        'GroundwaterProcess.run': {
            'scope': 'gw',
        },
        'DemandSiteProcess.run': {
            'scope': 'ds',
        },
        'RiverProcess.run': {
            'scope': 'river',
        },
    }
    time_functions = {}

    @staticmethod
    def get_scopes():
        scopes = set(['general'])
        for time_key in TimerSummary.config_summary:
            scopes.add(TimerSummary.config_summary[time_key]['scope'])

        return scopes

    @staticmethod
    def timeit(method):

        @wraps(method)
        def timed(*args, **kw):
            ts = time.time()
            result = method(*args, **kw)
            te = time.time()

            f_name = method.__qualname__

            if f_name in TimerSummary.config_summary:
                f_scope = TimerSummary.config_summary[f_name]['scope']
            else:
                f_scope = 'general'

            TimerSummary.time_functions[f_name] = {
                'scope': f_scope,
                'ms': (te - ts) * 1000
            }

            return result

        return timed

    @staticmethod
    def get_summary_time(f_scope: str = 'all'):
        ms_total_time = 0

        if f_scope == 'all':
            scopes = TimerSummary.get_scopes()
            for scope in scopes:
                ms_total_time += TimerSummary.get_summary_time(f_scope=scope)
        else:
            for method in TimerSummary.time_functions:
                scope = TimerSummary.time_functions[method]['scope']
                if f_scope == scope:
                    ms_total_time += TimerSummary.time_functions[method]['ms']

        return ms_total_time

    @staticmethod
    def get_summary_by_scope(f_scope: str = 'all'):
        summary = []
        # headers = ["function", "ms"]

        if f_scope == 'all':
            total_time_ms = 0
            scopes = TimerSummary.get_scopes()
            for scope in scopes:
                # TODO: watch if the total times were in order to calculate the total over totals
                _summary = TimerSummary.get_summary_by_scope(f_scope=scope)
                summary.append(_summary)
        else:
            for method in TimerSummary.time_functions:
                scope = TimerSummary.time_functions[method]['scope']
                ms = TimerSummary.time_functions[method]['ms']
                if f_scope == scope:
                    summary.append([(ui.bold, method), (ui.green, ms)])

            total_ms = TimerSummary.get_summary_time(f_scope = f_scope)
            summary.append([(ui.bold, 'Total: ' + f_scope), (ui.red, total_ms)])

        return summary

    @staticmethod
    def get_summary_by_function():
        summary = []
        total_time_ms = 0
        for method in TimerSummary.time_functions:
            scope = TimerSummary.time_functions[method]['scope']
            ms = TimerSummary.time_functions[method]['ms']

            total_time_ms += ms
            summary.append([(ui.bold, method), (ui.green, ms)])
        summary.append([(ui.bold, 'Total'), (ui.red, total_time_ms)])

        return summary


def signature_func(func, *args, **kwargs):
    args_repr = [repr(a) for a in args]  # 1
    kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]  # 2

    signature = ", ".join(args_repr + kwargs_repr)  # 3
    #print(f"Calling {func.__name__}({signature})")

    value = "{func.__name__}({signature})"

    return value




def main_task(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        args_dict = {}
        for k, v in kwargs.items():
            args_dict[k] = v

        summary = args[0]

        func_name = func.__name__
        msg_str = msg_config[func_name]

        #msg_info = Utils.insert_ui(text=msg_str.format(**args_dict))
        #ui.info(ui.green, ui.bold, '=> ', ui.white, ui.faint, *msg_info, ui.tabs(1), end=' ')
        # ui.info(ui.green, ui.bold, '=> ', ui.white, ui.faint, msg_str.format(**args_dict), ui.tabs(1), end=' ')

        _err, _errors = func(*args, **kwargs)
        if _err:
            msg_status = 'ERROR'
            #ui.info(ui.red, ui.bold, "[ERROR]")
        else:
            msg_status = 'OK'
            #ui.info(ui.green, ui.bold, "[OK]")

        # save msg into summary
        summary.set_process_line(msg_str, msg_status)

        return _err, _errors

    return wrapper




