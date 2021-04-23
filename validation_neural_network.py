import sys
import os
import gensim
import random
import numpy
import torch as torch
import torch.nn as nn
import torch.nn.functional as F
from time import time

from node_object_creator import *
from embeddings import Embedding
from node import Node
from matrix_generator import MatrixGenerator
from first_neural_network import First_neural_network
from coding_layer import Coding_layer
from convolutional_layer import Convolutional_layer
from pooling_layer import Pooling_layer
from dynamic_pooling import Max_pooling_layer, Dynamic_pooling_layer
from hidden_layer import Hidden_layer
from get_targets import GetTargets


class Validation_neural_network():

    def __init__(self, n = 20, m = 4, pooling = 'one-way pooling'):
        self.vector_size = n
        self.feature_size = m
        # parameters
        self.w_comb1 = None
        self.w_comb2 = None
        self.w_t = None
        self.w_r = None
        self.w_l = None
        self.b_conv = None
        self.w_hidden = None
        self.b_hidden = None
        # pooling method
        self.pooling = pooling
        if self.pooling == 'one-way pooling':
            self.pooling_layer = Pooling_layer()
        else:
            self.dynamic = Dynamic_pooling_layer()
            self.max_pool = Max_pooling_layer()
        # layers
        self.cod = None
        self.conv = None
        self.hidden = None


    def validation(self, validation_path):
        """Create the validation loop"""
        print('Validation stated')
        ### Validation set
        # this is to have all the information of each file in the folder contained in a dictionary
        validation_dict = self.validation_dict_set_up(validation_path)
        # this is the tensor with all target values
        targets = self.target_tensor_set_up(validation_path, validation_dict)

        ### Import the trained parameters in the training step and initialize all layers
        self.trained_params()

        # We calculate the predictions
        predicts = self.forward(validation_dict)
        # print the predictions
        print('predictions: \n', predicts)

        # Loss function
        criterion = nn.BCELoss()
        loss = criterion(predicts, targets)

        # TODO Build the accuracy evaluation method for each file
        # Confusion matrix

        print('Loss validation: ', loss)


    def validation_dict_set_up(self, validation_path):
        validation_dict = {}
        for (dirpath, _dirnames, filenames) in os.walk(validation_path):
            for filename in filenames:
                if filename.endswith('.py'):
                    filepath = os.path.join(dirpath, filename)
                    validation_dict[filepath] = None
        return validation_dict


    def target_tensor_set_up(self, validation_path, validation_dict):
        # Target dict initialization
        target = GetTargets(validation_path)
        targets_dict = target.df_iterator()
        print(targets_dict)
        targets = []
        for filepath in validation_dict.keys():
            # Targets' tensor creation
            search_target = filepath + '.csv'
            if search_target in targets_dict.keys():
                if targets == []:
                    targets = targets_dict[search_target]
                else:
                    targets = torch.cat((targets, targets_dict[search_target]), 0)
        print("target tensor:", targets)
        return targets


    def trained_params(self):
        '''Import the trained parameters of the second neural network'''
        ### Parameters
        w_comb1 = numpy.genfromtxt("params\\w_comb1.csv", delimiter = ",")
        self.w_comb1 = torch.tensor(w_comb1, dtype=torch.float32)
        w_comb2 = numpy.genfromtxt("params\\w_comb2.csv", delimiter = ",")
        self.w_comb2 = torch.tensor(w_comb2, dtype=torch.float32)
        w_t = numpy.genfromtxt("params\\w_t.csv", delimiter = ",")
        self.w_t = torch.tensor(w_t, dtype=torch.float32)
        w_r = numpy.genfromtxt("params\\w_r.csv", delimiter = ",")
        self.w_r = torch.tensor(w_r, dtype=torch.float32)
        w_l = numpy.genfromtxt("params\\w_l.csv", delimiter = ",")
        self.w_l = torch.tensor(w_l, dtype=torch.float32)
        b_conv = numpy.genfromtxt("params\\b_conv.csv", delimiter = ",")
        self.b_conv = torch.tensor(b_conv, dtype=torch.float32)
        w_hidden = numpy.genfromtxt("params\\w_hidden.csv", delimiter = ",")
        self.w_hidden = torch.tensor(w_hidden, dtype=torch.float32)
        b_hidden = numpy.genfromtxt("params\\b_hidden.csv", delimiter = ",")
        self.b_hidden = torch.tensor(b_hidden, dtype=torch.float32)

        ### Layers
        self.cod = Coding_layer(self.vector_size, self.w_comb1, self.w_comb2)
        self.conv = Convolutional_layer(self.vector_size, self.w_t, self.w_r, self.w_l, self.b_conv, features_size=self.feature_size)
        self.hidden = Hidden_layer(self.w_hidden, self.b_hidden)


    def forward(self, validation_dict):
        outputs = []
        softmax = nn.Sigmoid()
        for filepath in validation_dict:
            # first neural network
            validation_dict[filepath] = self.first_neural_network(filepath)
            
            ## forward (second neural network)
            output = self.second_neural_network(validation_dict[filepath])

            # output append
            if outputs == []:
                outputs = torch.tensor([softmax(output)])
            else:
                outputs = torch.cat((outputs, softmax(output)), 0)

        return outputs
    

    def first_neural_network(self, file, learning_rate = 0.1, momentum = 0.01):
        '''Initializing node list, dict list and dict sibling'''
        # we parse the data of the file into a tree
        tree = file_parser(file)
        # convert its nodes into the Node class we have, and assign their attributes
        ls_nodes, dict_ast_to_Node = node_object_creator(tree)
        ls_nodes = node_position_assign(ls_nodes)
        ls_nodes, dict_sibling = node_sibling_assign(ls_nodes)

        # Initializing vector embeddings
        embed = Embedding(self.vector_size, ls_nodes, dict_ast_to_Node)
        ls_nodes = embed.node_embedding()

        # Calculate the vector representation for each node
        vector_representation = First_neural_network(ls_nodes, dict_ast_to_Node, self.vector_size, learning_rate, momentum)
        ls_nodes, w_l_code, w_r_code, b_code = vector_representation.vector_representation()

        print("end vector representation of file:", file)
        return [ls_nodes, dict_ast_to_Node, dict_sibling, w_l_code, w_r_code, b_code]


    def second_neural_network(self, vector_representation_params):
        ls_nodes = vector_representation_params[0]
        dict_ast_to_Node = vector_representation_params[1]
        dict_sibling = vector_representation_params[2]
        w_l_code = vector_representation_params[3]
        w_r_code = vector_representation_params[4]
        b_code = vector_representation_params[5]
        ls_nodes = self.cod.coding_layer(ls_nodes, dict_ast_to_Node, w_l_code, w_r_code, b_code)
        ls_nodes = self.conv.convolutional_layer(ls_nodes, dict_ast_to_Node)
        if self.pooling == 'one-way pooling':
            vector = self.pooling_layer.pooling_layer(ls_nodes)
        else:
            self.max_pool.max_pooling(ls_nodes)
            vector = self.dynamic.three_way_pooling(ls_nodes, dict_sibling)
        output = self.hidden.hidden_layer(vector)

        return output
