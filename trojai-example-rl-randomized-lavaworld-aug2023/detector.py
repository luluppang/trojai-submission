# NIST-developed software is provided by NIST as a public service. You may use, copy and distribute copies of the software in any medium, provided that you keep intact this entire notice. You may improve, modify and create derivative works of the software or any portion of the software, and you may copy and distribute such modifications or works. Modified works should carry a notice stating that you changed the software and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the software.

# NIST-developed software is expressly provided "AS IS." NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED, IN FACT OR ARISING BY OPERATION OF LAW, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA ACCURACY. NIST NEITHER REPRESENTS NOR WARRANTS THAT THE OPERATION OF THE SOFTWARE WILL BE UNINTERRUPTED OR ERROR-FREE, OR THAT ANY DEFECTS WILL BE CORRECTED. NIST DOES NOT WARRANT OR MAKE ANY REPRESENTATIONS REGARDING THE USE OF THE SOFTWARE OR THE RESULTS THEREOF, INCLUDING BUT NOT LIMITED TO THE CORRECTNESS, ACCURACY, RELIABILITY, OR USEFULNESS OF THE SOFTWARE.

# You are solely responsible for determining the appropriateness of using and distributing the software and you assume all risks associated with its use, including but not limited to the risks and costs of program errors, compliance with applicable laws, damage to or loss of data, programs or equipment, and the unavailability or interruption of operation. This software is not intended to be used in any situation where a failure could cause risk of injury or damage to property. The software developed by NIST employees is not subject to copyright protection within the United States.


import logging
import os,sys
import argparse
import json
import jsonpickle
import pickle
import numpy as np
from joblib import dump, load

from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV

import feature_extractor_local as fe

from utils.abstract import AbstractDetector
from utils.model_utils import compute_action_from_trojai_rl_model
from utils.models import load_model, load_models_dirpath, ImageACModel, ResNetACModel

from utils.world import RandomLavaWorldEnv
from utils.wrappers import ObsEnvWrapper, TensorWrapper


class Detector(AbstractDetector):
    def __init__(self, metaparameter_filepath, learned_parameters_dirpath):
        """Detector initialization function.

        Args:
            metaparameter_filepath: str - File path to the metaparameters file.
            learned_parameters_dirpath: str - Path to the learned parameters directory.
        """
        metaparameters = json.load(open(metaparameter_filepath, "r"))

        self.metaparameter_filepath = metaparameter_filepath
        self.learned_parameters_dirpath = learned_parameters_dirpath
        # self.model_filepath = os.path.join(self.learned_parameters_dirpath, "model.bin")
        # self.models_padding_dict_filepath = os.path.join(self.learned_parameters_dirpath, "models_padding_dict.bin")
        # self.model_layer_map_filepath = os.path.join(self.learned_parameters_dirpath, "model_layer_map.bin")
        # self.layer_transform_filepath = os.path.join(self.learned_parameters_dirpath, "layer_transform.bin")
        #
        # self.input_features = metaparameters["train_input_features"]
        # self.weight_params = {
        #     "rso_seed": metaparameters["train_weight_rso_seed"],
        #     "mean": metaparameters["train_weight_params_mean"],
        #     "std": metaparameters["train_weight_params_std"],
        # }
        # self.random_forest_kwargs = {
        #     "n_estimators": metaparameters[
        #         "train_random_forest_regressor_param_n_estimators"
        #     ],
        #     "criterion": metaparameters[
        #         "train_random_forest_regressor_param_criterion"
        #     ],
        #     "max_depth": metaparameters[
        #         "train_random_forest_regressor_param_max_depth"
        #     ],
        #     "min_samples_split": metaparameters[
        #         "train_random_forest_regressor_param_min_samples_split"
        #     ],
        #     "min_samples_leaf": metaparameters[
        #         "train_random_forest_regressor_param_min_samples_leaf"
        #     ],
        #     "min_weight_fraction_leaf": metaparameters[
        #         "train_random_forest_regressor_param_min_weight_fraction_leaf"
        #     ],
        #     "max_features": metaparameters[
        #         "train_random_forest_regressor_param_max_features"
        #     ],
        #     "min_impurity_decrease": metaparameters[
        #         "train_random_forest_regressor_param_min_impurity_decrease"
        #     ],
        # }

    def write_metaparameters(self):
        metaparameters = {
            "train_input_features": self.input_features,
            "train_weight_rso_seed": self.weight_params["rso_seed"],
            "train_weight_params_mean": self.weight_params["mean"],
            "train_weight_params_std": self.weight_params["std"],
            "train_random_forest_regressor_param_n_estimators": self.random_forest_kwargs["n_estimators"],
            "train_random_forest_regressor_param_criterion": self.random_forest_kwargs["criterion"],
            "train_random_forest_regressor_param_max_depth": self.random_forest_kwargs["max_depth"],
            "train_random_forest_regressor_param_min_samples_split": self.random_forest_kwargs["min_samples_split"],
            "train_random_forest_regressor_param_min_samples_leaf": self.random_forest_kwargs["min_samples_leaf"],
            "train_random_forest_regressor_param_min_weight_fraction_leaf": self.random_forest_kwargs["min_weight_fraction_leaf"],
            "train_random_forest_regressor_param_max_features": self.random_forest_kwargs["max_features"],
            "train_random_forest_regressor_param_min_impurity_decrease": self.random_forest_kwargs["min_impurity_decrease"],
        }

        with open(os.path.join(self.learned_parameters_dirpath, os.path.basename(self.metaparameter_filepath)), "w") as fp:
            fp.write(jsonpickle.encode(metaparameters, warn=True, indent=2))

    def automatic_configure(self, models_dirpath: str):
        """Configuration of the detector iterating on some of the parameters from the
        metaparameter file, performing a grid search type approach to optimize these
        parameters.

        Args:
            models_dirpath: str - Path to the list of model to use for training
        """
        # for random_seed in np.random.randint(1000, 9999, 10):
        #     self.weight_params["rso_seed"] = random_seed
        #     self.manual_configure(models_dirpath)
        return self.manual_configure(models_dirpath)

    def manual_configure(self, models_dirpath: str):
        """Configuration of the detector using the parameters from the metaparameters
        JSON file.

        Args:
            models_dirpath: str - Path to the list of model to use for training
        """
        # Create the learned parameter folder if needed
        if not os.path.exists(self.learned_parameters_dirpath):
            os.makedirs(self.learned_parameters_dirpath)

        # get hyperparameters
        args = {}
        args['low_layer'] = 0
        args['high_layer'] = 3
        args['num_eigen_values'] = 15

        # List all available model
        model_path_list = sorted([os.path.join(models_dirpath, model) for model in os.listdir(models_dirpath)])
        logging.info(f"Loading %d models...", len(model_path_list))

        all_features_and_labels = fe.get_features_and_labels(args, model_path_list)
        model_A_features, model_A_labels = all_features_and_labels['model_A_features'], all_features_and_labels[
            'model_A_labels']
        # model_B_features, model_B_labels = all_features_and_labels['model_B_features'], all_features_and_labels[
        #     'model_B_labels']

        np.save('features_A', model_A_features)
        # np.save('features_B', model_B_features)
        np.save('labels_A', model_A_labels)
        # np.save('labels_B', model_B_labels)

        base_clf = RandomForestClassifier(n_estimators=2000, max_depth=2, criterion='log_loss', bootstrap=True,
                                          random_state=0)
        clf_A, clf_B, clf_C = CalibratedClassifierCV(base_estimator=base_clf, cv=5), CalibratedClassifierCV(
            base_estimator=base_clf, cv=5), CalibratedClassifierCV(base_estimator=base_clf, cv=5)
        clf_A.fit(model_A_features, model_A_labels)
        # clf_B.fit(model_B_features, model_B_labels)

        dump(clf_A, os.path.join(self.learned_parameters_dirpath, 'classifier_model_A.joblib'))
        # dump(clf_B, os.path.join(self.learned_parameters_dirpath, 'classifier_model_B.joblib'))

        # model_repr_dict, model_ground_truth_dict = load_models_dirpath(model_path_list)
        #
        # logging.info("Building RandomForest based on random features, with the provided mean and std.")
        # rso = np.random.RandomState(seed=self.weight_params['rso_seed'])
        # X = []
        # y = []
        # for model_arch in model_repr_dict.keys():
        #     for model_index in range(len(model_repr_dict[model_arch])):
        #         y.append(model_ground_truth_dict[model_arch][model_index])
        #
        #         model_feats = rso.normal(loc=self.weight_params['mean'], scale=self.weight_params['std'], size=(1,self.input_features))
        #         X.append(model_feats)
        # X = np.vstack(X)
        #
        # logging.info("Training RandomForestRegressor model.")
        # model = RandomForestRegressor(**self.random_forest_kwargs, random_state=0)
        # model.fit(X, y)
        #
        # logging.info("Saving RandomForestRegressor model...")
        # with open(self.model_filepath, "wb") as fp:
        #     pickle.dump(model, fp)
        #
        # self.write_metaparameters()
        logging.info("Configuration done!")

    def inference_on_example_data(self, model, examples_dirpath, config_dict):
        """Method to demonstrate how to inference on a round's example data.

        Args:
            model: the pytorch model
            examples_dirpath: the directory path for the round example data
        """

        size = config_dict["grid_size"]

        # device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # model.to(device)
        model.eval()

        # logging.info("Using compute device: {}".format(device))

        model_name = type(model).__name__
        observation_mode = "rgb" if model_name in [ImageACModel.__name__, ResNetACModel.__name__] else 'simple'

        wrapper_obs_mode = 'simple_rgb' if observation_mode == 'rgb' else 'simple'

        env = TensorWrapper(ObsEnvWrapper(RandomLavaWorldEnv(mode=observation_mode, grid_size=size), mode=wrapper_obs_mode))

        obs, info = env.reset()
        done = False
        max_iters = 1000
        iters = 0
        reward = 0

        while not done and iters < max_iters:
            env.render()
            action = compute_action_from_trojai_rl_model(model, obs, sample=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated

        logging.info('Final reward: {}'.format(reward))


    def infer(
            self,
            model_filepath,
            result_filepath,
            scratch_dirpath,
            examples_dirpath,
            round_training_dataset_dirpath,
    ):
        """Method to predict whether a model is poisoned (1) or clean (0).

        Args:
            model_filepath:
            result_filepath:
            scratch_dirpath:
            examples_dirpath:
            round_training_dataset_dirpath:
        """
        # get hyperparameters
        args = {}
        args['low_layer'] = 0
        args['high_layer'] = 3
        args['num_eigen_values'] = 15

        # predict_model_class_and_features = fe.get_model_features(args, model_filepath)
        predict_model_class_and_features = fe.get_general_model_features(args, model_filepath)
        predict_model_class = predict_model_class_and_features['model_class']
        predict_model_features = np.asarray([predict_model_class_and_features['features']])
        # if predict_model_class == 'FCModel':
        #     clf = load('/learned_parameters/classifier_model_A.joblib')
        #     probability = clf.predict_proba(predict_model_features)
        # elif predict_model_class == 'CNNModel':
        #     clf = load('/learned_parameters/classifier_model_B.joblib')
        #     probability = clf.predict_proba(predict_model_features)
        # else:
        #     logging.warning('No able to detect such model class')
        #     probability = [0.5, 0.5]
        clf = load('/learned_parameters/classifier_model_A.joblib')
        probability = clf.predict_proba(predict_model_features)
        logging.info('Trojan Probability of this class {} model is: {}'.format(predict_model_class, probability))

        # # load the model
        # model, model_repr, model_class = load_model(model_filepath)
        #
        # # Load the config file
        # config_dict = {}
        #
        # model_dirpath = os.path.dirname(model_filepath)
        #
        # config_filepath = os.path.join(model_dirpath, 'config.json')
        #
        # with open(config_filepath) as config_file:
        #     config_dict = json.load(config_file)
        #
        # # Inferences on examples to demonstrate how it is done for a round
        # self.inference_on_example_data(model, examples_dirpath, config_dict)
        #
        # # build a fake random feature vector for this model, in order to compute its probability of poisoning
        # rso = np.random.RandomState(seed=self.weight_params['rso_seed'])
        # X = rso.normal(loc=self.weight_params['mean'], scale=self.weight_params['std'], size=(1, self.input_features))
        #
        # # # create a random model for testing (fit to nothing)
        # # model = RandomForestRegressor(**self.random_forest_kwargs, random_state=0)
        # # model.fit(X, [0])
        # # with open(self.model_filepath, "wb") as fp:
        # #     pickle.dump(model, fp)
        #
        # # load the RandomForest from the learned-params location
        # with open(self.model_filepath, "rb") as fp:
        #     regressor: RandomForestRegressor = pickle.load(fp)
        #
        # # use the RandomForest to predict the trojan probability based on the feature vector X
        # probability = regressor.predict(X)[0]
        # # clip the probability to reasonable values
        # probability = np.clip(probability, a_min=0.01, a_max=0.99)

        # write the trojan probability to the output file
        with open(result_filepath, "w") as fp:
            fp.write(str(probability[0, -1]))

        logging.info("Trojan probability: {}".format(probability[0, -1]))
        return probability[0, -1]
