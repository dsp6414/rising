from __future__ import annotations

import os
import typing
import pathlib
from functools import partial
from tqdm import tqdm
import warnings

from torch.utils.data import Dataset as TorchDset
from rising.loading.debug_mode import get_debug_mode
from rising import AbstractMixin
from torch.multiprocessing import Pool


class Dataset(TorchDset):
    """
    Extension of PyTorch's Datasets by a ``get_subset`` method which returns a
    sub-dataset.
    """

    def get_subset(self, indices: typing.Sequence[int]) -> SubsetDataset:
        """
        Returns a Subset of the current dataset based on given indices

        Parameters
        ----------
        indices : iterable
            valid indices to extract subset from current dataset

        Returns
        -------
        :class:`SubsetDataset`
            the subset
        """
        # extract other important attributes from current dataset
        kwargs = {}

        for key, val in vars(self).items():
            if not (key.startswith("__") and key.endswith("__")):

                if key == "data":
                    continue
                kwargs[key] = val

        old_getitem = self.__class__.__getitem__
        subset_data = [self[idx] for idx in indices]

        return SubsetDataset(subset_data, old_getitem, **kwargs)


class SubsetDataset(Dataset):
    """
    A Dataset loading the data, which has been passed
    in it's ``__init__`` by it's ``_sample_fn``
    """

    def __init__(self, data: typing.Sequence, old_getitem: typing.Callable,
                 **kwargs):
        """
        Parameters
        ----------
        data : sequence
            data to load (subset of original data)
        old_getitem : function
            get item method of previous dataset
        **kwargs :
            additional keyword arguments (are set as class attribute)
        """
        super().__init__()

        self.data = data
        self._old_getitem = old_getitem

        for key, val in kwargs.items():
            setattr(self, key, val)

    def __getitem__(self, index: int) -> typing.Union[typing.Dict, typing.Any]:
        """
        returns single sample corresponding to ``index`` via the old get_item
        Parameters
        ----------
        index : int
            index specifying the data to load

        Returns
        -------
        Any, dict
            can be any object containing a single sample,
            but is often a dict-like.
        """
        return self._old_getitem(self, index)

    def __len__(self) -> int:
        """
        returns the length of the dataset

        Returns
        -------
        int
            number of samples
        """
        return len(self.data)


class CacheDataset(Dataset):
    def __init__(self,
                 data_path: typing.Union[typing.Union[pathlib.Path, str], list],
                 load_fn: typing.Callable,
                 mode: str = "append",
                 num_workers: int = None,
                 verbose=False,
                 **load_kwargs):
        """
        A dataset to preload all the data and cache it for the entire
        lifetime of this class.

        Parameters
        ----------
        data_path : str, Path or list
            the path(s) containing the actual data samples
        load_fn : function
            function to load the actual data
        mode : str
            whether to append the sample to a list or to extend the list by
            it. Supported modes are: :param:`append` and :param:`extend`.
            Default: ``append``
        num_workers : int, optional
            the number of workers to use for preloading. ``0`` means, all the
            data will be loaded in the main process, while ``None`` means,
            the number of processes will default to the number of logical
            cores.
        verbose : bool
            whether to show the loading progress. Mutually exclusive with
            ``num_workers is not None and num_workers > 0``
        **load_kwargs :
            additional keyword arguments. Passed directly to :param:`load_fn`
        """
        super().__init__()

        if get_debug_mode() and (num_workers is None or num_workers > 0):
            warnings.warn("The debug mode has been activated. "
                          "Falling back to num_workers = 0", UserWarning)
            num_workers = 0

        if (num_workers is None or num_workers > 0) and verbose:
            warnings.warn("Verbosity is mutually exclusive with "
                          "num_workers > 0. Setting it to False instead.", UserWarning)
            verbose = False

        self._num_workers = num_workers
        self._verbosity = verbose

        self._load_fn = load_fn
        self._load_kwargs = load_kwargs
        self.data = self._make_dataset(data_path, mode)

    def _make_dataset(self, path: typing.Union[typing.Union[pathlib.Path, str], list],
                      mode: str) -> typing.List[dict]:
        """
        Function to build the entire dataset

        Parameters
        ----------
        path : str, Path or list
            the path(s) containing the data samples
        mode : str
            whether to append or extend the dataset by the loaded sample

        Returns
        -------
        list
            the loaded data

        """
        data = []
        if not isinstance(path, list):
            assert os.path.isdir(path), '%s is not a valid directory' % path
            path = [os.path.join(path, p) for p in os.listdir(path)]

        # sort for reproducibility (this is done explicitly since the listdir
        # function does not return the paths in an ordered way on all OS)
        path = sorted(path)

        # add loading kwargs
        load_fn = partial(self._load_fn, **self._load_kwargs)

        # multiprocessing dispatch
        if self._num_workers is None or self._num_workers > 0:
            with Pool() as p:
                _data = p.map(load_fn, path)
        else:
            if self._verbosity:
                path = tqdm(path, unit='samples', desc="Loading Samples")
            _data = map(load_fn, path)

        for sample in _data:
            self._add_item(data, sample, mode)
        return data

    @staticmethod
    def _add_item(data: list, item: typing.Any, mode: str) -> None:
        """
        Adds items to the given data list. The actual way of adding these
        items depends on :param:`mode`

        Parameters
        ----------
        data : list
            the list containing the already loaded data
        item : Any
            the current item which will be added to the list
        mode : str
            the string specifying the mode of how the item should be added.

        """
        _mode = mode.lower()

        if _mode == 'append':
            data.append(item)
        elif _mode == 'extend':
            data.extend(item)
        else:
            raise TypeError(f"Unknown mode detected: {mode} not supported.")

    def __getitem__(self, index: int) -> typing.Union[typing.Any, typing.Dict]:
        """
        Making the whole Dataset indexeable.

        Parameters
        ----------
        index : int
            the integer specifying which sample to return

        Returns
        -------
        Any, Dict
            can be any object containing a single sample, but in practice is
            often a dict

        """
        return self.data[index]

    def __len__(self) -> int:
        """
        Length of dataset

        Returns
        -------
        int
            number of elements
        """
        return len(self.data)


class LazyDataset(Dataset):
    def __init__(self, data_path: typing.Union[str, list],
                 load_fn: typing.Callable,
                 **load_kwargs):
        """
        A dataset to load all the data just in time.

        Parameters
        ----------
        data_path : str, Path or list
            the path(s) containing the actual data samples
        load_fn : function
            function to load the actual data
        load_kwargs:
            additional keyword arguments (passed to :param:`load_fn`)
        """
        super().__init__()
        self._load_fn = load_fn
        self._load_kwargs = load_kwargs
        self.data = self._make_dataset(data_path)

    def _make_dataset(self, path: typing.Union[typing.Union[pathlib.Path, str],
                                               list]) -> typing.List[dict]:
        """
        Function to build the entire dataset

        Parameters
        ----------
        path : str, Path or list
            the path(s) containing the data samples

        Returns
        -------
        list
            the loaded data

        """
        if not isinstance(path, list):
            assert os.path.isdir(path), '%s is not a valid directory' % path
            path = [os.path.join(path, p) for p in os.listdir(path)]

        sorted(path)
        return path

    def __getitem__(self, index: int) -> dict:
        """
        Making the whole Dataset indexeable. Loads the necessary sample.

        Parameters
        ----------
        index : int
            the integer specifying which sample to load and return

        Returns
        -------
        Any, Dict
            can be any object containing a single sample, but in practice is
            often a dict

        """
        data_dict = self._load_fn(self.data[index],
                                  **self._load_kwargs)
        return data_dict

    def __len__(self) -> int:
        """
        Length of dataset

        Returns
        -------
        int
            number of elements
        """
        return len(self.data)


class IDManager(AbstractMixin):
    def __init__(self, id_key: str, cache_ids: bool = True, **kwargs):
        """
        Helper class to add additional functionality to Datasets

        Parameters
        ----------
        id_key : str
            the id key to cache
        cache_ids : bool
            whether to cache the ids
        **kwargs :
            additional keyword arguments
        """
        super().__init__(**kwargs)
        self.id_key = id_key
        self._cached_ids = None

        if cache_ids:
            self.cache_ids()

    def cache_ids(self) -> None:
        """
        Caches the IDs

        """
        self._cached_ids = {
            sample[self.id_key]: idx for idx, sample in enumerate(self)}

    def _find_index_iterative(self, id: str) -> int:
        """
        Checks for the next index matching the given id

        Parameters
        ----------
        id : str
            the id to get the index for

        Returns
        -------
        int
            the returned index

        Raises
        ------
        KeyError
            no index matching the given id

        """
        for idx, sample in enumerate(self):
            if sample[self.id_key] == id:
                return idx
        raise KeyError(f"ID {id} not found.")

    def get_sample_by_id(self, id: str) -> dict:
        """
        Fetches the sample to a corresponding ID

        Parameters
        ----------
        id : str
            the id specifying the sample to return

        Returns
        -------
        dict
            the sample corresponding to the given ID

        """
        return self[self.get_index_by_id(id)]

    def get_index_by_id(self, id: str) -> int:
        """
        Returns the index corresponding to a given id

        Parameters
        ----------
        id : str
            the id specifying the index of which sample should be returned

        Returns
        -------
        int
            the index of the sample matching the given id

        """
        if self._cached_ids is not None:
            return self._cached_ids[id]
        else:
            return self._find_index_iterative(id)


class CacheDatasetID(IDManager, CacheDataset):
    def __init__(self, data_path, load_fn, id_key, cache_ids=True,
                 **kwargs):
        """
        Caching version of ID Dataset

        Parameters
        ----------
        data_path : str, Path or list
            the path(s) containing the actual data samples
        load_fn : function
            function to load the actual data
        id_key : str
            the id key to cache
        cache_ids : bool
            whether to cache the ids
        **kwargs :
            additional keyword arguments
        """
        super().__init__(data_path=data_path, load_fn=load_fn, id_key=id_key,
                         cache_ids=cache_ids, **kwargs)


class LazyDatasetID(IDManager, LazyDataset):
    def __init__(self, data_path, load_fn, id_key, cache_ids=True,
                 **kwargs):
        """
        Lazy version of ID Dataset

        Parameters
        ----------
        data_path : str, Path or list
            the path(s) containing the actual data samples
        load_fn : function
            function to load the actual data
        id_key : str
            the id key to cache
        cache_ids : bool
            whether to cache the ids
        **kwargs :
            additional keyword arguments
        """
        super().__init__(data_path=data_path, load_fn=load_fn, id_key=id_key,
                         cache_ids=cache_ids, **kwargs)