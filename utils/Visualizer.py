import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors 
import seaborn as sns

class Visualizer:
    def __init__(self, directory_path):
        self.directory_path = directory_path

    def write_matrix_img(self, matrix, name, **kwargs):
        
        # Manage kwargs
        row_labels = kwargs.get('row_labels')
        column_labels = kwargs.get('column_labels')
        cbar = kwargs.get('cbar', False)
        cmap = kwargs.get('cmap', 'viridis')
        linewidth = kwargs.get('linewidth', 0)
        title = kwargs.get('title', None)
        legend = kwargs.get('legend', False)
        colors_list = kwargs.get('colors_list', None)
        color_labels = kwargs.get('color_labels', None)
        min_val = kwargs.get('min_val', None)
        max_val = kwargs.get('max_val', None)
        x_label = kwargs.get('x_label', None)
        y_label = kwargs.get('y_label', None)

        if colors_list:
            cmap = colors.ListedColormap(colors_list)
        elif cmap:
            cmap = cmap
        else:
            cmap = 'viridis'
        
        fig, ax = plt.subplots()

        cax = ax.imshow(matrix, cmap=cmap, interpolation='none')

        x_fontsize = min(10, 300//len(column_labels))
        y_fontsize = min(10, 300//len(row_labels))

        ax.set_xticks(range(len(column_labels)))
        ax.set_xticklabels(column_labels, fontsize= x_fontsize, rotation=90)

        ax.set_yticks(range(len(row_labels)), row_labels, fontsize= y_fontsize)
        ax.set_yticklabels(row_labels, fontsize= y_fontsize)

        ax.tick_params(top=False, bottom=True, labeltop=False, labelbottom=True)

        if linewidth>0:
            ax.set_xticks(np.arange(len(column_labels)+1)-0.5, minor=True)
            ax.set_yticks(np.arange(len(row_labels)+1)-0.5, minor=True)
            ax.grid(which="minor", color="w", linestyle='-', linewidth=linewidth) # change the appearance of your padding here
            ax.tick_params(which="minor", size=0)
            
        if cbar:
            if color_labels and min_val!=None and max_val!=None:
                interval = abs(min_val - max_val) / (len(color_labels))
                offset = interval/2 + min_val
                ticks = [(offset + i*interval) for i in range(len(color_labels))]
                cbar = fig.colorbar(cax, ticks=ticks, fraction=0.046, pad=0.04)
                cbar.ax.set_yticklabels(color_labels)
            else:
                cbar = fig.colorbar(cax, fraction=0.046, pad=0.04)

        if title:
            ax.set_title(title) 
            
        if x_label:
            ax.set_xlabel(x_label)
        if y_label:
            ax.set_ylabel(y_label)
        
        plt.savefig( self.directory_path + '/' + name + '.svg' , format='svg', bbox_inches='tight')
        plt.clf()


    def write_text_file(self, name, text=None, texts=None):
        if text:
            with open(self.directory_path + '/' + name + '.txt', 'w') as file:
                file.write(text)
        elif texts:
            with open(self.directory_path + '/' + name + '.txt', 'w') as file:
                for text in texts:
                    file.write(text + '\n')
