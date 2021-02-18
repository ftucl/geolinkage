from grass.pygrass.modules import MultiModule, ParallelModuleQueue

from Config import ConfigApp


class ProcessKernel:
    def __init__(self, config: ConfigApp):
        self.config = config
        # create container process modules
        feature_names = config.get_feature_names()

        self.modules_by_feature_limits = {}
        self.modules_by_feature_count = {}
        for feature in feature_names:
            self.modules_by_feature_limits[feature] = config.get_module_processing_limit(feature_type=feature)
            self.modules_by_feature_count[feature] = []

    def __run(self):
        queue = ParallelModuleQueue(nprocs=self.get_num_parallel_process() + 1)

        for feature in self.modules_by_feature_count:
            mm = MultiModule(module_list=self.modules_by_feature_count[feature], sync=False, set_temp_region=True)
            queue.put(mm)

        queue.wait()

        result_list = queue.get_finished_modules()
        for result in result_list:
            print('R: ' + str(result.popen.returncode))

    def get_num_parallel_process(self):
        return len(self.modules_by_feature_limits)

    def check_is_ready(self):
        is_ready = True
        for feature in self.modules_by_feature_count:
            limit = self.modules_by_feature_limits[feature]

            is_ready = is_ready and (len(self.modules_by_feature_count[feature]) == limit)

        return is_ready

    def add_module(self, feature_type: str, module=None, modules=None):
        if not(module and modules):
            print('ERROR PM')  # TODO: only for test, remove
            return

        modules = [module] if module else modules

        if feature_type in self.modules_by_feature_count:
            self.modules_by_feature_count[feature_type] += modules

            # check if processing is ready
            is_ok = self.check_is_ready()

            if is_ok:
                self.__run()
        else:  # TODO: only for test, remove
            print('error key: {}'.format(feature_type))

