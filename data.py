import numpy as np
import csv
import torch
import time
np.random.seed(2023)

def get_sequences(train_dict, validate_dict, num_item, max_seq_len, max_basket_len):
    sequences = list()
    for user in train_dict:
        sequences_user = list()
        # Pad each basket in the sequence up to max_basket_len (to the right)
        # sequences_user = [[1, 2, 3, 0, 0], [4, 5, 6, 7, 0], [8, 9, 10, 11, 12]] (0 is padding)
        # This contains the baskets for both training and validation

        for basket in train_dict[user] + [validate_dict[user]]:
            sequences_user.append(basket + [num_item] * (max_basket_len - len(basket)))
        # pad each sequence up to max_seq_len. If not enough long, pad to the left with empty baskets
        # where empty basket is represented by [num_item] * max_basket_len 
        # why + 2?
        sequences.append([[num_item] * max_basket_len] * (max_seq_len + 2 - len(sequences_user)) + sequences_user)
    sequences = np.array(sequences, dtype=np.int32)
    return sequences


def get_batches(sequences, batch_size):
    batches = list()
    idx = list(range(len(sequences)))
    np.random.shuffle(idx)
    i = 0
    while i < len(sequences):
        batches.append(sequences[idx[i:i+batch_size]])
        i += batch_size
    return batches


def get_inputs_train(num_item, batch):
    # 取到倒数第二个train basket做input，因为要predict最后一个basket
    # english version: get the second to last train basket as input, because we need to predict the last basket
    input_seq = batch[:, :-2, :]  # batch: [batch_size, train[0]...train[-2] train[-1] validate[], max_basket_len]
    # 需要预测的是这个。和train seq比向右移动了一位
    # english version: we need to predict this. Compared with the train seq, it is shifted to the right by one bit
    pred_seq = batch[:, 1:-1, :]

    # The following code is discarded for its excessive memory cost
    # if device == 'cuda':
    #     pred_seq = torch.tensor(pred_seq).long().to(device)
    #     mask = (pred_seq != 5).long().to(device)
    #     # Convert tensor a to one-hot encoding
    #     one_hot_pred = torch.nn.functional.one_hot(pred_seq, num_classes = num_item + 1).to(device)
    #     # Apply mask to one-hot tensor
    #     one_hot_pred = one_hot_pred * mask.unsqueeze(-1)
    #     # Sum one-hot tensor along the second axis to get multi-hot representation
    #     multi_hot_a = one_hot_pred.sum(dim=2)
    #     print("the multi_hot_a is", multi_hot_a)
    #     #Create a mask array to ignore padding item (num_item + 1)
    # elif device == 'cpu':
    # time1 =time.time()
    # mask = (pred_seq != num_item )
    # # Convert array a to one-hot encoding
    # one_hot_a = np.eye(num_item + 1, dtype= np.int8)[pred_seq]
    # # Apply mask to one-hot array
    # one_hot_a = one_hot_a * mask[..., None]
    # # Sum one-hot array along the second axis to get multi-hot representation
    # multi_hot_a = one_hot_a.sum(axis=2)
    # print("the shape of multi_hot_a is", multi_hot_a.shape)
    # time2 = time.time()
    # print("the time is", time2-time1)

    # else:
    #     raise ValueError("device must be 'cuda' or 'cpu'")

    labels_pred = list()
    for row in np.reshape(pred_seq, [-1, pred_seq.shape[-1]]):
        # chinese version:
        # 拆成一个个basket，然后为每一个basket生成一个label 向量，
        # 其中basket里面有item对应的位置为1，其他为0
        # english version:
        # split the pred_seq into baskets, and generate a label vector for each basket
        # the position of the item in the basket is 1, and the others are 0
        label_ = np.zeros(shape=num_item+1, dtype=np.float32)
        label_[row] = 1.0
        label_[-1] = 0.0 # the last item is padding item
        # labels.append(label_[:-1])
        labels_pred.append(label_)
    labels_pred = np.array(labels_pred) #
    labels_pred = np.reshape(labels_pred, [batch.shape[0], -1, num_item+1])


    return input_seq, labels_pred, pred_seq 

def load_dataset_batches(args):
    #### load dataset 
    # validate_dict and test_dict :
    # one user one basket
    # if a user has less than 3 basket, then no validate_dict nor test_dict
    [train_dict, validate_dict, test_dict, num_user, num_item] = np.load(f"{args.dataset}.npy", allow_pickle=True)
    if args.debug:
        num_user = 500 
        # take the first 500 users
        train_dict = {u: train_dict[u] for u in list(train_dict.keys())[:num_user]}
        validate_dict = {u: validate_dict[u] for u in list(validate_dict.keys())[:num_user]}
        test_dict = {u: test_dict[u] for u in list(test_dict.keys())[:num_user]}

    # print number of users and items
    print("num_user: %d, num_item: %d" % (num_user, num_item))

    # how many basket does each user have, whey + validate dict?
    seq_len = [len(train_dict[u] + [validate_dict[u]]) for u in train_dict]
    print("max seq len: %d, min seq len: %d, avg seq len: %.4f, med seq len: %.4f" % (np.max(seq_len), np.min(seq_len), np.mean(seq_len), np.median(seq_len)))



    # how may items does each basket have 
    basket_len = [len(b) for u in train_dict for b in train_dict[u] + [validate_dict[u]]]
    print("max basket len: %d, min basket len: %d, avg basket len: %.4f, med basket len: %.4f" % (np.max(basket_len), np.min(basket_len), np.mean(basket_len), np.median(basket_len)))
    args.max_seq_len, args.max_basket_len = np.max(seq_len), np.max(basket_len)

    # sequences = [num_user, max_seq_len (max number of baskets for a user among all users), max_basket_len (max number of items for a basket)]. elements are item_id, if item_i = num_item, then it is padding

    '''
     max_seq_len = 3, max_basket_len = 3, num_item = 5,
    sequences = [
        [ [5,5,5], [5,5,5], [3,2,5] ], // the fist two baskets are padding, the last basket has 2 items, 3 and 2, 5 is padding
        [ [5,5,5], [1,2,3], [4,5,6] ],
        .....
    ]
    '''
    sequences = get_sequences(train_dict, validate_dict, num_item, args.max_seq_len, args.max_basket_len)

    # split to batches
    batches = get_batches(sequences, args.batch_size) #(random_shuffle)

    return batches, num_user, num_item, train_dict, validate_dict, test_dict, sequences

def get_feed_dict_validate( batch):
    input_seq = batch[:, 1:-1, :]
    return input_seq 


def get_feed_dict_test( batch):
    input_seq = batch[:, 2:, :]
    return input_seq


def get_top_K_index(pred_scores, K):
    ind = np.argpartition(pred_scores, -K)[:, -K:]
    arr_ind = pred_scores[np.arange(len(pred_scores))[:, None], ind]
    arr_ind_argsort = np.argsort(arr_ind)[np.arange(len(pred_scores)), ::-1]
    batch_pred_list = ind[np.arange(len(pred_scores))[:, None], arr_ind_argsort]
    return batch_pred_list.tolist()

