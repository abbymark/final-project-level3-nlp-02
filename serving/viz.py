import re
import torch
import plotly.graph_objects as go
from utils import split_tensor_by_words, token_to_words

def format_attention(attention, layers=None, heads=None):
    if layers:
        attention = [attention[layer_index] for layer_index in layers]
    squeezed = []
    for layer_attention in attention:
        # 1 x num_heads x seq_len x seq_len
        if len(layer_attention.shape) != 4:
            raise ValueError("The attention tensor does not have the correct number of dimensions. Make sure you set "
                             "output_attentions=True when initializing your model.")
        layer_attention = layer_attention.squeeze(0)
        if heads:
            layer_attention = layer_attention[heads]
        squeezed.append(layer_attention)
    # num_layers x num_heads x seq_len x seq_len
    return torch.stack(squeezed)

def rgb_to_hex(r, g, b):
    r, g, b = int(r), int(g), int(b)
    return '#' + hex(r)[2:].zfill(2) + hex(g)[2:].zfill(2) + hex(b)[2:].zfill(2)

def highlighter(color, word):
    word = '<span style="background-color:' +color+ '">' +word+ '</span>'
    return word

def text_highlight(model, tokenizer, text, title) :
    encoder_input_ids = tokenizer(text, return_tensors="pt", add_special_tokens=True).input_ids
    decoder_input_ids = tokenizer(title, return_tensors="pt", add_special_tokens=True).input_ids

    encoder_text = tokenizer.convert_ids_to_tokens(encoder_input_ids[0])    
    
    outputs = model(input_ids=encoder_input_ids, decoder_input_ids=decoder_input_ids)

    st_cross_attention = format_attention(outputs.cross_attentions)

    layer_mat = st_cross_attention.detach()
    last_h_layer_mat = torch.mean(layer_mat, 1)[-1] ## mean by head side, last layer
    enc_mat = torch.mean(last_h_layer_mat, 0) ## mean by decoder id side

    enc_mat-= enc_mat.min()
    enc_mat /= enc_mat.max()
    
    colors = [rgb_to_hex(255, 255, 255*(1-attn_s)) for attn_s in enc_mat.numpy()]
    higlighted_text = ''.join([highlighter(colors[i], word) for i, word in enumerate(encoder_text)])
    higlighted_text = higlighted_text.replace('▁',' ')

    return higlighted_text

def cross_attention(model, tokenizer, text, title, model_type) :
    encoder_input_ids = tokenizer(text, return_tensors="pt", add_special_tokens=True).input_ids
    decoder_input_ids = tokenizer(title, return_tensors="pt", add_special_tokens=True).input_ids

    encoder_tokens = tokenizer.convert_ids_to_tokens(encoder_input_ids[0])
    decoder_tokens = tokenizer.convert_ids_to_tokens(decoder_input_ids[0])
    
    outputs = model(input_ids=encoder_input_ids, decoder_input_ids=decoder_input_ids)

    st_cross_attention = format_attention(outputs.cross_attentions)

    layer_mat = st_cross_attention.detach()
    last_h_layer_mat = torch.mean(layer_mat, 1)[-1] ## mean by head side, last layer

    dec_split_words_indices = split_tensor_by_words(decoder_tokens, model_type)
    enc_split_words_indices = split_tensor_by_words(encoder_tokens, model_type)

    dec_space_split_text = token_to_words(decoder_tokens, model_type)
    enc_space_split_text = token_to_words(encoder_tokens, model_type)

    print('attn_shape:', last_h_layer_mat.shape)
    print('dec_space_split_text:', dec_space_split_text)
    print('dec_indices:', dec_split_words_indices)
    splited_by_spaces = torch.split(last_h_layer_mat, dec_split_words_indices, dim=0)
    merging_tensor = []
    for split_tensor in splited_by_spaces :
        merging_tensor.append(torch.mean(split_tensor, 0))
    merged_attn = torch.stack(merging_tensor, dim=0)

    splited_by_spaces = torch.split(merged_attn, enc_split_words_indices, dim=1)
    merging_tensor = []
    for split_tensor in splited_by_spaces :
        merging_tensor.append(torch.mean(split_tensor, 1))
    merged_attn = torch.stack(merging_tensor, dim=1)

    go_fig = go.Figure(go.Heatmap(
                    z=merged_attn,
                    x=enc_space_split_text,
                    y=dec_space_split_text,
                    colorscale='Reds',
                    hoverongaps=False))
    go_fig.update_layout(
        autosize=False,
        width=1200,
        height=500,
        yaxis_autorange="reversed",
        margin=dict(l=10, r=20, t=20, b=20)
    )
    go_fig.update_xaxes(tickangle = 45)
    return go_fig