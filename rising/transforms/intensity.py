import torch
from typing import Union, Sequence

from rising.transforms.abstract import (BaseTransform, PerSampleTransform,
                                        PerChannelTransform)
from rising.transforms.functional.intensity import (
    norm_range,
    norm_min_max,
    norm_mean_std,
    norm_zero_mean_unit_std,
    add_noise,
    gamma_correction,
    add_value,
    scale_by_value,
    clamp)
from rising.random import AbstractParameter

__all__ = ["Clamp", "NormRange", "NormMinMax",
           "NormZeroMeanUnitStd", "NormMeanStd", "Noise",
           "GaussianNoise", "ExponentialNoise", "GammaCorrection",
           "RandomValuePerChannel", "RandomAddValue", "RandomScaleValue"]


class Clamp(BaseTransform):
    """Apply augment_fn to keys"""

    def __init__(self, min: Union[float, AbstractParameter],
                 max: Union[float, AbstractParameter],
                 keys: Sequence = ('data',), grad: bool = False, **kwargs):
        """


        Args:
            min: minimal value
            max: maximal value
            keys: the keys corresponding to the values to clamp
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to augment_fn
        """
        super().__init__(augment_fn=clamp, keys=keys, grad=grad,
                         min=min, max=max, property_names=('min', 'max'),
                         **kwargs)


class NormRange(PerSampleTransform):
    def __init__(self, min: Union[float, AbstractParameter],
                 max: Union[float, AbstractParameter], keys: Sequence = ('data',),
                 per_channel: bool = True,
                 grad: bool = False, **kwargs):
        """
        Args:
            min: minimal value
            max: maximal value
            keys: keys to normalize
            per_channel: normalize per channel
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to normalization function
        """
        super().__init__(augment_fn=norm_range, keys=keys, grad=grad,
                         min=min, max=max, per_channel=per_channel,
                         property_names=('min', 'max'), **kwargs)


class NormMinMax(PerSampleTransform):
    """Norm to [0, 1]"""

    def __init__(self, keys: Sequence = ('data',), per_channel: bool = True,
                 grad: bool = False, **kwargs):
        """
        Args:
            keys: keys to normalize
            per_channel: normalize per channel
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to normalization function
        """
        super().__init__(augment_fn=norm_min_max, keys=keys, grad=grad,
                         per_channel=per_channel, **kwargs)


class NormZeroMeanUnitStd(PerSampleTransform):
    """Normalize mean to zero and std to one"""

    def __init__(self, keys: Sequence = ('data',), per_channel: bool = True,
                 grad: bool = False, **kwargs):
        """
        Args:
            keys: keys to normalize
            per_channel: normalize per channel
            grad: enable gradient computation inside transformation
            kwargs: keyword arguments passed to normalization function
        """
        super().__init__(augment_fn=norm_zero_mean_unit_std, keys=keys,
                         grad=grad,
                         per_channel=per_channel, **kwargs)


class NormMeanStd(PerSampleTransform):
    """Normalize mean and std with provided values"""

    def __init__(self, mean: Union[float, Sequence[float]],
                 std: Union[float, Sequence[float]],
                 keys: Sequence[str] = ('data',), per_channel: bool = True,
                 grad: bool = False, **kwargs):
        """
        Args:
            mean: used for mean normalization
            std: used for std normalization
            keys: keys to normalize
            per_channel: normalize per channel
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to normalization function
        """
        super().__init__(augment_fn=norm_mean_std, keys=keys, grad=grad,
                         mean=mean, std=std, per_channel=per_channel, **kwargs)


class Noise(PerChannelTransform):
    """Add noise to data"""

    def __init__(self, noise_type: str, per_channel: bool = False,
                 keys: Sequence = ('data',), grad: bool = False, **kwargs):
        """
        Args:
            noise_type: supports all inplace functions of a
                :class:`torch.Tensor`
            per_channel: enable transformation per channel
            keys: keys to normalize
            grad: enable gradient computation inside transformation
            kwargs: keyword arguments passed to noise function
        See Also
        --------
        :func:`torch.Tensor.normal_`, :func:`torch.Tensor.exponential_`
        """
        super().__init__(augment_fn=add_noise, per_channel=per_channel, keys=keys,
                         grad=grad, noise_type=noise_type, **kwargs)


class ExponentialNoise(Noise):
    """Add exponential noise to data"""

    def __init__(self, lambd: float, keys: Sequence = ('data',),
                 grad: bool = False, **kwargs):
        """
        Args:
            lambd: lambda of exponential distribution
            keys: keys to normalize
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to noise function
        """
        super().__init__(noise_type='exponential_', lambd=lambd, keys=keys,
                         grad=grad, **kwargs)


class GaussianNoise(Noise):
    """Add gaussian noise to data"""

    def __init__(self, mean: float, std: float, keys: Sequence = ('data',),
                 grad: bool = False, **kwargs):
        """
        Args:
            mean: mean of normal distribution
            std: std of normal distribution
            keys: keys to normalize
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to noise function
        """
        super().__init__(noise_type='normal_', mean=mean, std=std, keys=keys,
                         grad=grad, **kwargs)


class GammaCorrection(BaseTransform):
    """Apply Gamma correction"""

    def __init__(self, gamma: Union[float, AbstractParameter],
                 keys: Sequence = ('data',), grad: bool = False, **kwargs):
        """
        Args:
            gamma: define gamma
            keys: keys to normalize
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to superclass
        """
        super().__init__(augment_fn=gamma_correction, gamma=gamma,
                         property_names=("gamma",), keys=keys, grad=grad,
                         **kwargs)


class RandomValuePerChannel(PerChannelTransform):
    """
    Apply augmentations which take random values as input by keyword
    :attr:`value`
    """

    def __init__(self, augment_fn: callable,
                 random_sampler: AbstractParameter,
                 per_channel: bool = False, keys: Sequence = ('data',),
                 grad: bool = False, **kwargs):
        """
        Args:
            augment_fn: augmentation function
            random_mode: specifies distribution which should be used to
                sample additive value. All function from python's random
                module are supported
            random_args: positional arguments passed for random function
            per_channel: enable transformation per channel
            keys: keys which should be augmented
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to augment_fn
        """
        super().__init__(augment_fn=augment_fn, per_channel=per_channel,
                         keys=keys, grad=grad, random_sampler=random_sampler,
                         property_names=('random_sampler',),
                         **kwargs)

    def forward(self, **data) -> dict:
        """
        Perform Augmentation.

        Args:
            data: dict with data

        Returns:
            dict: augmented data
        """
        if self.per_channel:
            seed = torch.random.get_rng_state()
            for _key in self.keys:
                torch.random.set_rng_state(seed)
                out = torch.empty_like(data[_key])
                for _i in range(data[_key].shape[1]):
                    rand_value = self.random_sampler
                    out[:, _i] = self.augment_fn(
                        data[_key][:, _i], value=rand_value, out=out[:, _i],
                        **self.kwargs)
                data[_key] = out
        else:
            rand_value = self.random_sampler
            for _key in self.keys:
                data[_key] = self.augment_fn(data[_key], value=rand_value, **self.kwargs)
        return data


class RandomAddValue(RandomValuePerChannel):
    """Increase values additively"""

    def __init__(self, random_sampler: AbstractParameter,
                 per_channel: bool = False,
                 keys: Sequence = ('data',), grad: bool = False, **kwargs):
        """
        Args:
            random_sampler: specify values to add
            per_channel: enable transformation per channel
            keys: keys which should be augmented
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to augment_fn
        """
        super().__init__(augment_fn=add_value, random_sampler=random_sampler,
                         per_channel=per_channel, keys=keys, grad=grad, **kwargs)


class RandomScaleValue(RandomValuePerChannel):
    """Scale Values"""

    def __init__(self, random_sampler: AbstractParameter,
                 per_channel: bool = False,
                 keys: Sequence = ('data',), grad: bool = False, **kwargs):
        """
        Args:
            random_sampler: specify values to add
            per_channel: enable transformation per channel
            keys: keys which should be augmented
            grad: enable gradient computation inside transformation
            **kwargs: keyword arguments passed to augment_fn
        """
        super().__init__(augment_fn=scale_by_value, random_sampler=random_sampler,
                         per_channel=per_channel, keys=keys, grad=grad, **kwargs)
