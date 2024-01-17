import torch
import torch.nn as nn
import torch.nn.functional as F

from training.core.isomaxplus import IsoMaxPlusLossSecondPart
from training.core.logitnorm import LogitNormLoss


class OhemCELoss(nn.Module):
    def __init__(self, thresh, ignore_index=255):
        super(OhemCELoss, self).__init__()
        self.thresh = -torch.log(torch.tensor(thresh, requires_grad=False, dtype=torch.float)).cuda()
        self.ignore_index = ignore_index
        self.criteria = nn.CrossEntropyLoss(ignore_index=ignore_index)

    def forward(self, logits, labels):
        n_min = labels[labels != self.ignore_index].numel() // 16
        loss = self.criteria(logits, labels).view(-1)
        loss_hard = loss[loss > self.thresh]
        if loss_hard.numel() < n_min:
            loss_hard, _ = loss.topk(n_min)
        return torch.mean(loss_hard)


def get_loss_fn(config, device):
    if config.class_weights is None:
        weights = None
    else:
        weights = torch.Tensor(config.class_weights).to(device)

    if config.loss_type == 'ce':
        # Cross Entropy
        print('Warning: reduction is None, loss will be summed.')
        criterion = nn.CrossEntropyLoss(ignore_index=config.ignore_index, weight=weights)
    elif config.loss_type == 'ohem':
        criterion = OhemCELoss(thresh=config.ohem_thrs, ignore_index=config.ignore_index)  
    elif config.kd_loss_type == 'eiml':
        # Enhanced Isotropy Maximization Loss
        criterion = IsoMaxPlusLossSecondPart()
    elif config.kd_loss_type == 'ln':
        # Logit Normalization
        criterion = LogitNormLoss()
    else:
        raise NotImplementedError(f"Unsupport loss type: {config.loss_type}")
        
    return criterion
    
    
def kd_loss_fn(config, outputs, outputsT):
    if config.kd_loss_type == 'kl_div':
        lossT = F.kl_div(F.log_softmax(outputs/config.kd_temperature, dim=1),
                    F.softmax(outputsT.detach()/config.kd_temperature, dim=1)) * config.kd_temperature ** 2
                    
    elif config.kd_loss_type == 'mse':
        lossT = F.mse_loss(outputs, outputsT.detach())
        
    return lossT