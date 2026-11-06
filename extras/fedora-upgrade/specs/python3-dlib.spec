%global debug_package %{nil}
Name: python3-dlib
Version: 20.0.1
Release: 1.local%{?dist}
Summary: Dlib Python bindings built locally for facial authentication
License: BSL-1.0
URL: https://github.com/davisking/dlib
Source0: dlib-%{version}.tar.gz
BuildRequires: gcc-c++, cmake, python3-devel, python3-setuptools
Requires: python(abi) = %{python3_version}
Provides: python3dist(dlib) = %{version}
Provides: python%{python3_version}dist(dlib) = %{version}

%description
Python bindings built from the official dlib source distribution.

%prep
%setup -q -n dlib-%{version}

%build
export CMAKE_BUILD_PARALLEL_LEVEL=2
/usr/bin/python3 setup.py build

%install
/usr/bin/python3 setup.py install --skip-build --root=%{buildroot} --prefix=/usr --install-lib=%{python3_sitearch}

%check
PYTHONPATH=%{buildroot}%{python3_sitearch} /usr/bin/python3 -c "import dlib; print(dlib.__version__); dlib.get_frontal_face_detector()"

%files
%license dlib/LICENSE.txt
%{python3_sitearch}/dlib*
%{python3_sitearch}/_dlib_pybind11*
