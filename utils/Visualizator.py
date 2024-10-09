import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

class Visualizator:
    def __init__(self, directory_path):
        self.directory_path = directory_path

    def write_matrix_img(self, matrix, name, row_labels=None, column_labels=None, cmap='viridis'):

        sns.set_theme(font_scale=0.5)
        ax = sns.heatmap(matrix, cmap=cmap, xticklabels=column_labels, yticklabels=row_labels, linewidths=0.5)

        figure = ax.get_figure()

        # if row_labels:
        #     ax.set_yticks(np.arange(len(row_labels)))
        #     ax.set_yticklabels(row_labels, fontsize=8)
        
        # if column_labels:
        #     ax.set_xticks(np.arange(len(column_labels)))
        #     ax.set_xticklabels(column_labels, fontsize=8)
        #     plt.xticks(rotation=90)

        dpi = max(len(row_labels), len(column_labels)) if row_labels and column_labels else 10

        figure.savefig( self.directory_path + '/' + name + '.jpg', dpi = dpi , bbox_inches='tight')
