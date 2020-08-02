# 
# @author: Allan
#

import torch
import torch.nn as nn

from model.module.bilstm_encoder import BiLSTMEncoder
from model.module.linear_crf_inferencer import LinearCRF
from model.module.linear_encoder import LinearEncoder
from model.embedder import BertEmbedder
from typing import Tuple
from overrides import overrides


class BertNNCRF(nn.Module):

    def __init__(self, config, print_info: bool = True):
        super(BertNNCRF, self).__init__()
        self.device = config.device
        self.embedder = BertEmbedder(config, print_info=print_info)
        if config.hidden_dim > 0:
            self.encoder = BiLSTMEncoder(config, self.embedder.get_output_dim(), print_info=print_info)
        else:
            self.encoder = LinearEncoder(config, self.embedder.get_output_dim(), print_info=print_info)
        self.inferencer = LinearCRF(config, print_info=print_info)

    @overrides
    def forward(self, words: torch.Tensor,
                    word_seq_lens: torch.Tensor,
                    orig_to_tok_index: torch.Tensor,
                    input_mask: torch.Tensor,
                    labels: torch.Tensor) -> torch.Tensor:
        """
        Calculate the negative loglikelihood.
        :param words: (batch_size x max_seq_len)
        :param word_seq_lens: (batch_size)
        :param context_emb: (batch_size x max_seq_len x context_emb_size)
        :param chars: (batch_size x max_seq_len x max_char_len)
        :param char_seq_lens: (batch_size x max_seq_len)
        :param labels: (batch_size x max_seq_len)
        :return: the total negative log-likelihood loss
        """
        word_rep = self.embedder(words, orig_to_tok_index, input_mask)
        lstm_scores = self.encoder(word_rep, word_seq_lens)
        batch_size = word_rep.size(0)
        sent_len = word_rep.size(1)
        maskTemp = torch.arange(1, sent_len + 1, dtype=torch.long).view(1, sent_len).expand(batch_size, sent_len).to(self.device)
        mask = torch.le(maskTemp, word_seq_lens.view(batch_size, 1).expand(batch_size, sent_len)).to(self.device)
        unlabed_score, labeled_score =  self.inferencer(lstm_scores, word_seq_lens, labels, mask)
        return unlabed_score - labeled_score

    def decode(self, words: torch.Tensor,
                    word_seq_lens: torch.Tensor,
                    orig_to_tok_index: torch.Tensor,
                    input_mask,
                    **kwargs) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Decode the batch input
        :param batchInput:
        :return:
        """
        word_rep = self.embedder(words, orig_to_tok_index, input_mask)
        features = self.encoder(word_rep, word_seq_lens)
        bestScores, decodeIdx = self.inferencer.decode(features, word_seq_lens)
        return bestScores, decodeIdx