import numpy as np
import matplotlib.pyplot as plt

class Visualizator:
    def __init__(self, directory_path):
        self.directory_path = directory_path

    def write_matrix_img(self, matrix, name, row_labels=None, column_labels=None, cmap='viridis'):
        fig, ax = plt.subplots()

        cax = ax.matshow(matrix, cmap=cmap) 

        if row_labels:
            ax.set_yticks(np.arange(len(row_labels)))
            ax.set_yticklabels(row_labels)
        
        if column_labels:
            ax.set_xticks(np.arange(len(column_labels)))
            ax.set_xticklabels(column_labels)
            plt.xticks(rotation=90)

        plt.savefig( self.directory_path + '/' + name + '.png', bbox_inches='tight')
