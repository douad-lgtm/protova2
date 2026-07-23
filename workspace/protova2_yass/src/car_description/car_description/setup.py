from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'car_description'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),

        # ── Launch files ─────────────────────────
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),

        # ── URDF ────────────────────────────────
        (os.path.join('share', package_name, 'urdf'),
            glob('urdf/*.urdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='protova2',
    maintainer_email='yassine.mathlouthi@alten.com',
    description='Car description pkg',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
        ],
    },
)