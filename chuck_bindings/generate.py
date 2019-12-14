from chuck_bindings.chuck_module import ChuckModule


def main():
    filename = '_chuck.cpp'
    with open(filename, 'wt') as f:
        chuck_module = ChuckModule()
        chuck_module.generate(f)
        print('Generated file {}'.format(filename))


if __name__ == '__main__':
    main()
