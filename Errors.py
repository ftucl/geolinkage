import ui
import re

import Utils
from Config import ConfigApp


class ErrorManager:
    def __init__(self, config: ConfigApp):

        self.config = config

        self._errors = {}
        self._errors_meta = {}
        self._warnings = {}
        self._warnings_meta = {}

        for feature in self.config.type_names:
            f_type = self.config.type_names[feature]
            self._errors[f_type] = []
            self._warnings[f_type] = []

            self._errors_meta[f_type] = {}  #
            self._warnings_meta[f_type] = {}

        self._errors['other'] = []
        self._errors['rf'] = []  # return flows
        self._errors['ri'] = []  # runoff infiltrations
        self._errors['tl'] = []  # transmission links

        self._warnings['other'] = []
        self._warnings['rf'] = []  # return flows
        self._warnings['ri'] = []  # runoff infiltrations
        self._warnings['tl'] = []  # transmission links

        self._errors_meta['other'] = {}
        self._warnings_meta['other'] = {}

    def get_error_types(self):
        return list(self._errors.keys())

    def check_warning(self, types: list = None, typ: str = None, code: str = ''):
        if code:
            if typ:
                if typ in self._warnings_meta and code in self._warnings_meta[typ]:
                    return len(self._warnings_meta[typ]) > 0
                elif 'other' in self._warnings_meta and code in self._warnings_meta['other']:
                    return len(self._warnings_meta['other'][code]) > 0
                else:
                    return False
            elif types:
                _err = False
                for typ in types:
                    _err = _err or self.check_warning(typ=typ, code=code)
                return _err
            else:
                return self.check_warning(types=list(self._warnings_meta.keys()))  # all errors
        else:
            if typ:
                if typ in self._warnings:
                    return len(self._warnings[typ]) > 0
                else:
                    return len(self._warnings['other']) > 0
            elif types:
                _err = False
                for typ in types:
                    _err = _err or self.check_warning(typ=typ)
                return _err
            else:
                return self.check_warning(types=list(self._warnings.keys()))  # all errors

    def check_error(self, types: list = None, typ: str = None, code: str = ''):
        if code:
            if typ:
                if typ in self._errors_meta and code in self._errors_meta[typ]:
                    return len(self._errors_meta[typ]) > 0
                elif 'other' in self._errors_meta and code in self._errors_meta['other']:
                    return len(self._errors_meta['other'][code]) > 0
                else:
                    return False
            elif types:
                _err = False
                for typ in types:
                    _err = _err or self.check_error(typ=typ, code=code)
                return _err
            else:
                return self.check_error(types=list(self._errors_meta.keys()))  # all errors
        else:
            if typ:
                if typ in self._errors:
                    return len(self._errors[typ]) > 0
                else:
                    return len(self._errors['other']) > 0
            elif types:
                _err = False
                for typ in types:
                    _err = _err or self.check_error(typ=typ)
                return _err
            else:
                return self.check_error(types=list(self._errors.keys()))  # all errors

    def append(self, msg: str, typ: str = 'other', is_warn: bool = False, code: str = ''):
        if is_warn:
            if typ in self._warnings:
                self._warnings[typ].append(msg)
            else:
                self._warnings['other'].append(msg)
        else:
            if typ in self._errors:
                self._errors[typ].append(msg)
            else:
                self._errors['other'].append(msg)

        self.add_metadata(msg=msg, typ=typ, code=code, is_warn=is_warn) if code else None

    def add_metadata(self, msg: str, typ: str = 'other', is_warn: bool = False, code: str = ''):
        if is_warn:
            if typ in self._warnings_meta:
                if code in self._warnings_meta[typ]:
                    self._warnings_meta[typ][code].append(msg)
                else:
                    self._warnings_meta[typ][code] = [msg]
            else:
                if code in self._warnings_meta['other']:
                    self._warnings_meta['other'][code].append(msg)
                else:
                    self._warnings_meta['other'][code] = [msg]
        else:
            if typ in self._errors_meta:
                if code in self._errors_meta[typ]:
                    self._errors_meta[typ][code].append(msg)
                else:
                    self._errors_meta[typ][code] = [msg]
            else:
                if code in self._errors_meta['other']:
                    self._errors_meta['other'][code].append(msg)
                else:
                    self._errors_meta['other'][code] = [msg]

    def get_errors(self, typ: str = '', types: list = None, code: str = ''):
        effect = 'ui.bold ui.red'
        normal = 'ui.ui.faint ui.white'

        if code:
            errors = []
            if typ in self._errors_meta and code in self._errors_meta[typ]:
                for _err in self._errors_meta[typ][code]:
                    errors.append(_err)
        else:
            if typ:
                if typ in self._errors:
                    errors = self._errors[typ]
                else:  # error key does not exist
                    errors = self._errors['other']
            elif types:
                errors = []
                for typ in types:
                    errors += self.get_errors(typ=typ)
            else:
                errors = self.get_errors(types=list(self._errors.keys()))

        return errors

    def get_warnings(self, typ: str = '', types: list = None, code: str = ''):
        effect = 'ui.bold ui.red'
        normal = 'ui.ui.faint ui.white'

        if code:
            errors = []
            if typ in self._warnings_meta and code in self._warnings_meta[typ]:
                for _err in self._warnings_meta[typ][code]:
                    errors.append(_err)
        else:
            if typ:
                if typ in self._warnings:
                    errors = self._warnings[typ]
                else:  # error key does not exist
                    errors = self._warnings['other']
            elif types:
                errors = []
                for typ in types:
                    errors += self.get_warnings(typ=typ)
            else:
                errors = self.get_warnings(types=list(self._warnings.keys()))

        return errors

    def print(self, typ: str = '', types: list = None, is_warn: bool = False):
        if is_warn:
            if typ:
                errors = self.get_warnings(typ=typ)
            elif types:
                errors = self.get_warnings(types=types)
            else:  # all errors
                errors = self.get_warnings(types=list(self._errors.keys()))

            for ind, err in enumerate(errors):
                ui.info(ui.tabs(1), '[WARNING {}] '.format(ind + 1), err)
        else:
            if typ:
                errors = self.get_errors(typ=typ)
            elif types:
                errors = self.get_errors(types=types)
            else:  # all errors
                errors = self.get_errors(types=list(self._errors.keys()))

            for ind, err in enumerate(errors):
                ui.info(ui.tabs(1), '[ERROR {}] '.format(ind+1), err)

    def print_ui(self, typ: str = '', types: list = None, is_warn: bool = False):
        if is_warn:
            if typ:
                errors = self.get_warnings(typ=typ)
            elif types:
                errors = self.get_warnings(types=types)
            else:  # all errors
                errors = self.get_warnings(types=list(self._errors.keys()))

            for ind, err in enumerate(errors):
                err_ui_list = Utils.insert_ui(err)
                ui.info(ui.tabs(1), '[WARNING {}] '.format(ind + 1), *err_ui_list)
        else:
            if typ:
                errors = self.get_errors(typ=typ)
            elif types:
                errors = self.get_errors(types=types)
            else:  # all errors
                errors = self.get_errors(types=list(self._errors.keys()))

            for ind, err in enumerate(errors):
                err_ui_list = Utils.insert_ui(err)
                ui.info(ui.tabs(1), '[ERROR {}] '.format(ind + 1), *err_ui_list)

