import torch
import torch.nn as nn
import torch.optim as optim
import os
import numpy as np
from model import Model
from utils import load_data, get_config, load_data_new
from tqdm import tqdm
from torch.utils.data import DataLoader, TensorDataset
import wandb
import matplotlib.pyplot as plt


def train(agent, loader):
    pbar = tqdm(total=config.epochs)
    best_loss = np.inf

    for epoch in range(config.epochs):
        agent.train()
        total_loss = 0.0
        for batch in loader:
            s, g, a, s1 = batch
            loss, loss_dict = agent.training_step((
                s.to(agent.device),
                g.to(agent.device),
                a.to(agent.device),
                s1.to(agent.device)
            ))
            total_loss += loss

        if (epoch + 1) % 100 == 0:
            avg_loss = total_loss / len(loader)

            log_dict = {'train_loss': avg_loss, **loss_dict}
            wandb.log(log_dict)

            if avg_loss < best_loss:
                # save best params
                path_save = os.path.join(os.getcwd(), config.save_dir)
                best_loss = avg_loss
                os.makedirs(path_save, exist_ok=True)
                agent.save_model(os.path.join(path_save, f'model_{config.task}_{hz}.pth'))

            states = data[0]
            goals = data[1]
            actions = data[2].numpy()
            acts = agent.policy(
                states.to(agent.device),
                goals.to(agent.device)
            ).detach().cpu().numpy()

            plt.scatter(acts[:, 0], acts[:, 2], s=1, color='blue', zorder=2)
            plt.scatter(actions[:, 0], actions[:, 2], s=10, color='red', zorder=1)
            plt.savefig(os.path.join(os.getcwd(), 'figures', f'actions.png'))
            plt.close()
        pbar.update()

    pbar.close()
    return best_loss


def main():
    #device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    dataloader = DataLoader(TensorDataset(*data), batch_size=config.batch_size, shuffle=True)

    agent = Model(
        input_size=data[0].shape[-1],
        goal_size=data[1].shape[-1],
        action_size=data[2].shape[-1],
        N_gaussians=config.N_gaussians,
        device=config.device
    )

    best_score = train(agent, dataloader)

    print(f'Training finished with best score of {best_score}')


if __name__ == "__main__":
    config = get_config('config/hyperparameters.yaml')

    config.wb_mode = 'online' #'offline' #'online'
    config.wb_group = 'new_params_trials'

    hz = 10

    parent_dir = os.path.dirname(os.getcwd())
    data, ee_positions = load_data_new(
        data_path=os.path.join(parent_dir, config.load_dir, config.task),
        n_frames=config.n_frames,
        frequency=hz
    )

    wb_run = f'{config.task}_data_spline'
    wandb.init(project="Behavioural_cloning", config=config, name=wb_run,
               mode=config.wb_mode, group=config.wb_group)

    main()

