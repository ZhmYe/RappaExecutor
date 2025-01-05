import time

from ctgan import CTGAN, load_demo
import torch
import pickle

# 加载真实数据
real_data = load_demo()

# 离散列的名称
discrete_columns = [
    'workclass',
    'education',
    'marital-status',
    'occupation',
    'relationship',
    'race',
    'sex',
    'native-country',
    'income'
]

# 训练 CTGAN
ctgan = CTGAN(epochs=10)
ctgan.fit(real_data, discrete_columns)
startTime = time.time()
print(ctgan.sample(10))
print(time.time() - startTime)
def save_ctgan(ctgan, filepath):
    """
    保存 CTGAN 模型到 .pth 文件。

    Args:
        ctgan: 训练好的 CTGAN 模型。
        filepath: 保存路径，例如 'ctgan_model.pth'。
    """
    # 保存生成器的权重
    generator_state = ctgan._generator.state_dict()
    # 保存数据转换器配置
    transformer_config = pickle.dumps(ctgan._transformer)

    # 动态计算 data_dim
    data_dim = ctgan._transformer.output_dimensions

    # 保存元数据
    metadata = {
        'embedding_dim': ctgan._embedding_dim,
        'generator_dim': ctgan._generator_dim,
        'discriminator_dim': ctgan._discriminator_dim,
        'generator_lr': ctgan._generator_lr,
        'discriminator_lr': ctgan._discriminator_lr,
        'batch_size': ctgan._batch_size,
        'epochs': ctgan._epochs,
        'discrete_columns': discrete_columns,
        'data_dim': data_dim,  # 关键：保存数据维度信息
        'cond_dim': ctgan._data_sampler.dim_cond_vec()
    }

    # 将所有内容打包保存
    torch.save({
        'generator_state': generator_state,
        'transformer_config': transformer_config,
        'metadata': metadata
    }, filepath)
    with open("test/sampler", 'wb') as f:
        pickle.dump(ctgan._data_sampler, f)

# 调用保存函数
save_ctgan(ctgan, 'test/ctgan_model.pth')
print("CTGAN 模型已保存为 'ctgan_model.pth'")

