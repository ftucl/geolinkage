import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

class Visualizator:
    def __init__(self, directory_path):
        self.directory_path = directory_path

    def write_matrix_img(self, matrix, name, row_labels=None, column_labels=None, cmap='viridis'
                        , cbar = False, linewidth = 0):

        sns.set_theme(font_scale=0.5)
        ax = sns.heatmap(matrix, cmap=cmap, xticklabels=column_labels, yticklabels=row_labels, cbar=cbar,  linewidths=linewidth, linecolor='white')

        figure = ax.get_figure()

        figure.savefig( self.directory_path + '/' + name + '.svg' , format='svg', bbox_inches='tight')
