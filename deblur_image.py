import os
import argparse
import math

from tqdm import tqdm
from torchvision.transforms.functional import to_pil_image
import torch

import model.model as module_arch
from data_loader.data_loader import CustomDataLoader
from utils.util import denormalize


def main(blurred_dir, deblurred_dir, resume):
    # load checkpoint
    checkpoint = torch.load(resume)
    config = checkpoint['config']

    # setup data_loader instances
    data_loader = CustomDataLoader(data_dir=blurred_dir)

    # build model architecture
    generator_class = getattr(module_arch, config['generator']['type'])
    generator = generator_class(**config['generator']['args'])

    # prepare model for deblurring
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    generator.to(device)
    if config['n_gpu'] > 1:
        generator = torch.nn.DataParallel(generator)

    generator.load_state_dict(checkpoint['generator'])

    generator.eval()

    # start to deblur
    with torch.no_grad():
        for batch_idx, sample in enumerate(tqdm(data_loader, ascii=True)):
            blurred = sample['blurred'].to(device)
            image_name = sample['image_name'][0]

            # crop the image to 256*256 patches and feed them into the GAN
            deblurred = torch.zeros_like(blurred)
            N, C, H, W = blurred.size()
            fine_size_h = fine_size_w = 256
            h_patch_num = math.ceil(H / fine_size_h)
            w_patch_num = math.ceil(W / fine_size_w)
            for i in range(h_patch_num):
                for j in range(w_patch_num):
                    deblurred[:, :, i * fine_size_h:(i + 1) * fine_size_h, j * fine_size_w:(j + 1) * fine_size_w] \
                        = generator(
                        blurred[:, :, i * fine_size_h:(i + 1) * fine_size_h, j * fine_size_w:(j + 1) * fine_size_w])

            deblurred_img = to_pil_image(denormalize(deblurred).squeeze().cpu())

            deblurred_img.save(os.path.join(deblurred_dir, 'deblurred ' + image_name))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Deblur your own image!')

    parser.add_argument('-b', '--blurred', required=True, type=str, help='dir of blurred images')
    parser.add_argument('-d', '--deblurred', required=True, type=str, help='dir to save deblurred images')
    parser.add_argument('-r', '--resume', required=True, type=str, help='path to latest checkpoint')
    parser.add_argument('--device', default=None, type=str, help='indices of GPUs to enable (default: all)')

    args = parser.parse_args()

    if args.device:
        os.environ["CUDA_VISIBLE_DEVICES"] = args.device

    main(args.blurred, args.deblurred, args.resume)
