import torch
import torch.nn as nn
import torch.nn.functional as F

from seq2seq import utils
from seq2seq.models import Seq2SeqModel, Seq2SeqEncoder, Seq2SeqDecoder
from seq2seq.models import register_model, register_model_architecture

import logging
@register_model('lstm')
class LSTMModel(Seq2SeqModel):
    """ Defines the sequence-to-sequence model class. """

    def __init__(self,
                 encoder,
                 decoder):

        super().__init__(encoder, decoder)

    @staticmethod
    def add_args(parser):
        """Add model-specific arguments to the parser."""
        parser.add_argument('--encoder-embed-dim', type=int, help='encoder embedding dimension')
        parser.add_argument('--encoder-embed-path', help='path to pre-trained encoder embedding')
        parser.add_argument('--encoder-hidden-size', type=int, help='encoder hidden size')
        parser.add_argument('--encoder-num-layers', type=int, help='number of encoder layers')
        parser.add_argument('--encoder-bidirectional', help='bidirectional encoder')
        parser.add_argument('--encoder-dropout-in', help='dropout probability for encoder input embedding')
        parser.add_argument('--encoder-dropout-out', help='dropout probability for encoder output')

        parser.add_argument('--decoder-embed-dim', type=int, help='decoder embedding dimension')
        parser.add_argument('--decoder-embed-path', help='path to pre-trained decoder embedding')
        parser.add_argument('--decoder-hidden-size', type=int, help='decoder hidden size')
        parser.add_argument('--decoder-num-layers', type=int, help='number of decoder layers')
        parser.add_argument('--decoder-dropout-in', type=float, help='dropout probability for decoder input embedding')
        parser.add_argument('--decoder-dropout-out', type=float, help='dropout probability for decoder output')
        parser.add_argument('--decoder-use-attention', help='decoder attention')
        parser.add_argument('--decoder-use-lexical-model', help='toggle for the lexical model')

    @classmethod
    def build_model(cls, args, src_dict, tgt_dict):
        """ Constructs the model. """
        base_architecture(args)
        encoder_pretrained_embedding = None
        decoder_pretrained_embedding = None

        # Load pre-trained embeddings, if desired
        if args.encoder_embed_path:
            encoder_pretrained_embedding = utils.load_embedding(args.encoder_embed_path, src_dict)
        if args.decoder_embed_path:
            decoder_pretrained_embedding = utils.load_embedding(args.decoder_embed_path, tgt_dict)

        # Construct the encoder
        encoder = LSTMEncoder(dictionary=src_dict,
                              embed_dim=args.encoder_embed_dim,
                              hidden_size=args.encoder_hidden_size,
                              num_layers=args.encoder_num_layers,
                              bidirectional=args.encoder_bidirectional,
                              dropout_in=args.encoder_dropout_in,
                              dropout_out=args.encoder_dropout_out,
                              pretrained_embedding=encoder_pretrained_embedding)

        # Construct the decoder
        decoder = LSTMDecoder(dictionary=tgt_dict,
                              embed_dim=args.decoder_embed_dim,
                              hidden_size=args.decoder_hidden_size,
                              num_layers=args.decoder_num_layers,
                              dropout_in=args.decoder_dropout_in,
                              dropout_out=args.decoder_dropout_out,
                              pretrained_embedding=decoder_pretrained_embedding,
                              use_attention=bool(eval(args.decoder_use_attention)),
                              use_lexical_model=bool(eval(args.decoder_use_lexical_model)))
        return cls(encoder, decoder)


class LSTMEncoder(Seq2SeqEncoder):
    """ Defines the encoder class. """

    def __init__(self,
                 dictionary,
                 embed_dim=64,
                 hidden_size=64,
                 num_layers=1,
                 bidirectional=True,
                 dropout_in=0.25,
                 dropout_out=0.25,
                 pretrained_embedding=None):

        super().__init__(dictionary)

        self.dropout_in = dropout_in
        self.dropout_out = dropout_out
        self.bidirectional = bidirectional
        self.hidden_size = hidden_size
        self.output_dim = 2 * hidden_size if bidirectional else hidden_size

        if pretrained_embedding is not None:
            self.embedding = pretrained_embedding
        else:
            self.embedding = nn.Embedding(len(dictionary), embed_dim, dictionary.pad_idx)

        dropout_lstm = dropout_out if num_layers > 1 else 0.
        self.lstm = nn.LSTM(input_size=embed_dim,
                            hidden_size=hidden_size,
                            num_layers=num_layers,
                            dropout=dropout_lstm,
                            bidirectional=bidirectional)

    def forward(self, src_tokens, src_lengths):
        """ Performs a single forward pass through the instantiated encoder sub-network. """
        # Embed tokens and apply dropout
        batch_size, src_time_steps = src_tokens.size()
        src_embeddings = self.embedding(src_tokens)
        _src_embeddings = F.dropout(src_embeddings, p=self.dropout_in, training=self.training)

        # Transpose batch: [batch_size, src_time_steps, num_features] -> [src_time_steps, batch_size, num_features]
        src_embeddings = _src_embeddings.transpose(0, 1)

        # Pack embedded tokens into a PackedSequence
        packed_source_embeddings = nn.utils.rnn.pack_padded_sequence(src_embeddings, src_lengths)

        # Pass source input through the recurrent layer(s)
        packed_outputs, (final_hidden_states, final_cell_states) = self.lstm(packed_source_embeddings)

        # Unpack LSTM outputs and optionally apply dropout (dropout currently disabled)
        lstm_output, _ = nn.utils.rnn.pad_packed_sequence(packed_outputs, padding_value=0.)
        lstm_output = F.dropout(lstm_output, p=self.dropout_out, training=self.training)
        assert list(lstm_output.size()) == [src_time_steps, batch_size, self.output_dim]  # sanity check

        '''
        ___QUESTION-1-DESCRIBE-A-START___
        Describe what happens when self.bidirectional is set to True. 
        What is the difference between final_hidden_states and final_cell_states?
        
        When self.bidirectional is true, the LSTM is bidirectional and the original final_hidden_states 
        and final_cell_states are of shape (num_layers * num_directions, batch, hidden_size), where num_directions 
        here is exactly 2. What the if-block here does is to, for each layer of LSTM (if several LSTMs are stacked), 
        concatenate the vectors of the two directions into one vector. In other words, the new final_cell_states and 
        final_hidden_states will be of shape (num_layers, batch, num_directions * hidden_size).
        
        final_hidden_states are the hidden states (h_t) from the last (from the forward view) cells of different layers while
        the final_cell_states are the cell states (c_t) from the last (from the forward view) cells of different layers. 
        
        '''
        if self.bidirectional:
            def combine_directions(outs):
                return torch.cat([outs[0: outs.size(0): 2], outs[1: outs.size(0): 2]], dim=2)
            final_hidden_states = combine_directions(final_hidden_states)
            final_cell_states = combine_directions(final_cell_states)
        '''___QUESTION-1-DESCRIBE-A-END___'''

        # Generate mask zeroing-out padded positions in encoder inputs
        src_mask = src_tokens.eq(self.dictionary.pad_idx)
        return {'src_embeddings': _src_embeddings.transpose(0, 1),
                'src_out': (lstm_output, final_hidden_states, final_cell_states),
                'src_mask': src_mask if src_mask.any() else None}


class AttentionLayer(nn.Module):
    """ Defines the attention layer class. Uses Luong's global attention with the general scoring function. """
    def __init__(self, input_dims, output_dims):
        super().__init__()
        # Scoring method is 'general'
        self.src_projection = nn.Linear(input_dims, output_dims, bias=False)
        self.context_plus_hidden_projection = nn.Linear(input_dims + output_dims, output_dims, bias=False)

    def forward(self, tgt_input, encoder_out, src_mask):
        # tgt_input has shape = [batch_size, input_dims]
        # encoder_out has shape = [src_time_steps, batch_size, output_dims]
        # src_mask has shape = [src_time_steps, batch_size]

        # Get attention scores
        encoder_out = encoder_out.transpose(1, 0)
        attn_scores = self.score(tgt_input, encoder_out)
        # (batch, 1, time)
        '''
        ___QUESTION-1-DESCRIBE-B-START___
        Describe how the attention context vector is calculated. 
        Why do we need to apply a mask to the attention scores?
        
        Given attention scores wrt different timestep t, 
        a mask is first applied to set scores of certain positions to 0.
        attn_score of shape (batch_size, 1, src_time_steps) is then fed into the softmax layer to normalize.
        Attention context vector is then obtained by matrix multiplication of attn_weigts of shape
         (batch_size, 1, src_time_steps)and encoder_out of shape (batch_size, src_time_steps, output_dim),
         resulting a tensor of shape (batch, 1, output_dim)  
         
        The reason for applying a mask is that the input sequence might be padded with 0 
        and thus the decoder should not attend to these padded subsequence (their attention scores
        are then masked to -inf). 
        '''
        if src_mask is not None:
            src_mask = src_mask.unsqueeze(dim=1)
            attn_scores.masked_fill_(src_mask, float('-inf'))
        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_context = torch.bmm(attn_weights, encoder_out).squeeze(dim=1)

        # (batch, 1, time), (batch, time, output_dim) -> (batch, 1, output_dim)

        context_plus_hidden = torch.cat([tgt_input, attn_context], dim=1)
        attn_out = torch.tanh(self.context_plus_hidden_projection(context_plus_hidden))

        '''___QUESTION-1-DESCRIBE-B-END___'''
        # first: next input_feed, transformation of [target hidden vector, context vector]
        # second: softmax-normalized attention weights
        return attn_out, attn_weights.squeeze(dim=1)

    def score(self, tgt_input, encoder_out):
        """ Computes attention scores. """

        '''
        ___QUESTION-1-DESCRIBE-C-START___
        How are attention scores calculated? 
        What role does matrix multiplication (i.e. torch.bmm()) play 
        in aligning encoder and decoder representations?
        
        Given a target vector t and encoder hidden state h, the attention scores is calculated by t^T A h 
        for some matrix A.
         
        The batch matrix multiplication computes dot products between projected encoder hidden states and the target input vector
        for every batch, which shows the similarities between the target vector and the hidden states.
        '''
        # encoder_out: (batch, time, output_dim)
        projected_encoder_out = self.src_projection(encoder_out).transpose(2, 1)
        # (batch, time, input_dims) -> (batch, input_dims, time)
        attn_scores = torch.bmm(tgt_input.unsqueeze(dim=1), projected_encoder_out)
        # (batch, 1, input_dims), (batch, input_dims, time) -> (batch, 1, time)
        '''___QUESTION-1-DESCRIBE-C-END___'''

        return attn_scores


class LSTMDecoder(Seq2SeqDecoder):
    """ Defines the decoder class. """

    def __init__(self,
                 dictionary,
                 embed_dim=64,
                 hidden_size=128,
                 num_layers=1,
                 dropout_in=0.25,
                 dropout_out=0.25,
                 pretrained_embedding=None,
                 use_attention=True,
                 use_lexical_model=False):

        super().__init__(dictionary)

        self.dropout_in = dropout_in
        self.dropout_out = dropout_out
        self.embed_dim = embed_dim
        self.hidden_size = hidden_size

        if pretrained_embedding is not None:
            self.embedding = pretrained_embedding
        else:
            self.embedding = nn.Embedding(len(dictionary), embed_dim, dictionary.pad_idx)

        # Define decoder layers and modules
        self.attention = AttentionLayer(hidden_size, hidden_size) if use_attention else None

        self.layers = nn.ModuleList([nn.LSTMCell(
            input_size=hidden_size + embed_dim if layer == 0 else hidden_size,
            hidden_size=hidden_size)
            for layer in range(num_layers)])

        self.final_projection = nn.Linear(hidden_size, len(dictionary))

        self.use_lexical_model = use_lexical_model
        if self.use_lexical_model:
            # __QUESTION: Add parts of decoder architecture corresponding to the LEXICAL MODEL here
            self.W_lexical_embed = nn.Linear(embed_dim, embed_dim, bias=False)
            self.W_lexical_output = nn.Linear(embed_dim, len(dictionary))
            # TODO: --------------------------------------------------------------------- /CUT

    def forward(self, tgt_inputs, encoder_out, incremental_state=None):
        """ Performs the forward pass through the instantiated model. """
        # Optionally, feed decoder input token-by-token
        if incremental_state is not None:
            tgt_inputs = tgt_inputs[:, -1:]

        # __QUESTION : Following code is to assist with the LEXICAL MODEL implementation
        # Recover encoder input
        # [src_time_steps, batch_size, num_features]
        src_embeddings = encoder_out['src_embeddings']

        src_out, src_hidden_states, src_cell_states = encoder_out['src_out']
        src_mask = encoder_out['src_mask']
        src_time_steps = src_out.size(0)

        # Embed target tokens and apply dropout
        batch_size, tgt_time_steps = tgt_inputs.size()
        tgt_embeddings = self.embedding(tgt_inputs)
        tgt_embeddings = F.dropout(tgt_embeddings, p=self.dropout_in, training=self.training)

        # Transpose batch: [batch_size, tgt_time_steps, num_features] -> [tgt_time_steps, batch_size, num_features]
        tgt_embeddings = tgt_embeddings.transpose(0, 1)

        # Initialize previous states (or retrieve from cache during incremental generation)
        '''
        ___QUESTION-1-DESCRIBE-D-START___
        Describe how the decoder state is initialized. When is cached_state == None? What role does input_feed play?
        
        If the cached_state exists, the decoder states are initialized to the contents from it. Otherwise, they are 
        initialized as zeros.
        
        The seq2seq model predicts one word at a time. The first time the seq2seq model, the decoder states (i.e. the 
        previous hidden state and the previous cell state) are initialized as 0, which is the case the cached_state is None.
        
        input_feed (i.e. input feeding from [Luong 2015]) propagates information about attention vector and target vector 
        of the previous timestep, which is helpful for modelling target words.
        '''
        cached_state = utils.get_incremental_state(self, incremental_state, 'cached_state')
        if cached_state is not None:
            tgt_hidden_states, tgt_cell_states, input_feed = cached_state
        else:
            # tgt_hidden_states = [torch.zeros(tgt_inputs.size()[0], self.hidden_size) for i in range(len(self.layers))]
            tgt_hidden_states = [src_embeddings.new_full((tgt_inputs.size()[0], self.hidden_size),0)
                                 for _ in range(len(self.layers))]
            # tgt_inputs: (batch_size, time_steps)
            # tgt_cell_states = [torch.zeros(tgt_inputs.size()[0], self.hidden_size) for i in range(len(self.layers))]
            tgt_cell_states = [src_embeddings.new_full((tgt_inputs.size()[0], self.hidden_size),fill_value=0)
                               for _ in range(len(self.layers))]
            # print(tgt_hidden_states[0].device, tgt_cell_states[0].device)
            input_feed = tgt_embeddings.data.new(batch_size, self.hidden_size).zero_()
            # tgt_embedding: (time_steps, batch_size, num_features)
        '''___QUESTION-1-DESCRIBE-D-END___'''

        # Initialize attention output node
        attn_weights = tgt_embeddings.data.new(batch_size, tgt_time_steps, src_time_steps).zero_()
        rnn_outputs = []

        # __QUESTION : Following code is to assist with the LEXICAL MODEL implementation
        # Cache lexical context vectors per translation time-step
        lexical_contexts = []

        for j in range(tgt_time_steps):
            # Concatenate the current token embedding with output from previous time step (i.e. 'input feeding')
            lstm_input = torch.cat([tgt_embeddings[j, :, :], input_feed], dim=1)

            for layer_id, rnn_layer in enumerate(self.layers):
                # Pass target input through the recurrent layer(s)
                tgt_hidden_states[layer_id], tgt_cell_states[layer_id] = \
                    rnn_layer(lstm_input, (tgt_hidden_states[layer_id], tgt_cell_states[layer_id]))

                # Current hidden state becomes input to the subsequent layer; apply dropout
                lstm_input = F.dropout(tgt_hidden_states[layer_id], p=self.dropout_out, training=self.training)

            '''
            ___QUESTION-1-DESCRIBE-E-START___
            How is attention integrated into the decoder? 
            Why is the attention function given the current target state as one of its inputs? 
            What is the purpose of the dropout layer?
            
            
            After the hidden state vector h_t from the top layer of stacked LSTM is computed,
            the decoder uses h_t and encoder hidden states to compute the attention vector (i.e. input feeding for next timestep).
            
            The attention function needs to measure the similarities between the current decoding state and every encoder hidden state 
            to obtain the attention weights (and vector). The previous target state encodes information about the current decoding state.
            
            The dropout layer randomly sets some positions to 0, which would potentially prevent overfitting. 
            In the case of decoding, the dropout could prevent the next decoding state from relying too much on some certain states of 
            attention vector.
            
            '''
            if self.attention is None:
                input_feed = tgt_hidden_states[-1]
            else:
                input_feed, step_attn_weights = self.attention(tgt_hidden_states[-1], src_out, src_mask)
                attn_weights[:, j, :] = step_attn_weights
                # attn_weight: (batch_size, tgt_time_step, src_time_step)
                if self.use_lexical_model:
                    # __QUESTION: Compute and collect LEXICAL MODEL context vectors here
                    # TODO: --------------------------------------------------------------------- CUT
                    # unsqueeze: (batch, timesteps) -> (batch, 1 ,timesteps)
                    # transpose: (timesteps, batch, hidden) -> (batch, timesteps, hidden)
                    lexical_contexts.append(
                            torch.matmul(torch.unsqueeze(step_attn_weights,1),
                                         src_embeddings.transpose(0,1)))
                    # logging.info(lexical_contexts[0].size())

                    # TODO: --------------------------------------------------------------------- /CUT

            input_feed = F.dropout(input_feed, p=self.dropout_out, training=self.training)
            rnn_outputs.append(input_feed)
            '''___QUESTION-1-DESCRIBE-E-END___'''

        # Cache previous states (only used during incremental, auto-regressive generation)
        utils.set_incremental_state(
            self, incremental_state, 'cached_state', (tgt_hidden_states, tgt_cell_states, input_feed))

        # Collect outputs across time steps
        decoder_output = torch.cat(rnn_outputs, dim=0).view(tgt_time_steps, batch_size, self.hidden_size)

        # Transpose batch back: [tgt_time_steps, batch_size, num_features] -> [batch_size, tgt_time_steps, num_features]
        decoder_output = decoder_output.transpose(0, 1)

        # Final projection
        decoder_output = self.final_projection(decoder_output)

        if self.use_lexical_model:
            # __QUESTION: Incorporate the LEXICAL MODEL into the prediction of target tokens here
            # (batch, timesteps, hidden)
            # logging.info(len(lexical_contexts))
            weighted_embeddings = torch.cat(lexical_contexts,1)
            activated_weighted_embeddings = F.tanh(weighted_embeddings)

            # logging.info(weighted_embeddings.size())
            # (batch, timesteps, embed)
            lexical_hidden = F.tanh(self.W_lexical_embed(activated_weighted_embeddings))+activated_weighted_embeddings
            decoder_output += self.W_lexical_output(lexical_hidden)
            # TODO: --------------------------------------------------------------------- /CUT

        return decoder_output, attn_weights


@register_model_architecture('lstm', 'lstm')
def base_architecture(args):
    args.encoder_embed_dim = getattr(args, 'encoder_embed_dim', 64)
    args.encoder_embed_path = getattr(args, 'encoder_embed_path', None)
    args.encoder_hidden_size = getattr(args, 'encoder_hidden_size', 64)
    args.encoder_num_layers = getattr(args, 'encoder_num_layers', 1)
    args.encoder_bidirectional = getattr(args, 'encoder_bidirectional', 'True')
    args.encoder_dropout_in = getattr(args, 'encoder_dropout_in', 0.25)
    args.encoder_dropout_out = getattr(args, 'encoder_dropout_out', 0.25)

    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 64)
    args.decoder_embed_path = getattr(args, 'decoder_embed_path', None)
    args.decoder_hidden_size = getattr(args, 'decoder_hidden_size', 128)
    args.decoder_num_layers = getattr(args, 'decoder_num_layers', 1)
    args.decoder_dropout_in = getattr(args, 'decoder_dropout_in', 0.25)
    args.decoder_dropout_out = getattr(args, 'decoder_dropout_out', 0.25)
    args.decoder_use_attention = getattr(args, 'decoder_use_attention', 'True')
    args.decoder_use_lexical_model = getattr(args, 'decoder_use_lexical_model', 'False')
