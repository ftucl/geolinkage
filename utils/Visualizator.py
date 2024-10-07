import numpy as np
import matplotlib.pyplot as plt

class Visualizator:
    def __init__(self):
        pass

    def show_dict_as_matrix(self, dictionary):
        matrix = []
        for key, value in dictionary.items():
            matrix.append(value)
        matrix = np.array(matrix)
        plt.imshow(matrix)
        plt.colorbar()
        plt.show()
        