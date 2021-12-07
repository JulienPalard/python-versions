from cycler import cycler
import numpy as np
import matplotlib.pyplot as plt

x = np.linspace(0, 2 * np.pi, 50)
offsets = np.linspace(0, 2 * np.pi, 4, endpoint=False)
yy = np.transpose([np.sin(x + phi) for phi in offsets])


plt.rc("axes", prop_cycle=cycler(linestyle=["-", "--", ":", "-."]))

# fig, (ax0, ax1) = plt.subplots(nrows=2)
plt.plot(yy)
# ax0.set_title("Set default color cycle to rgby")

# Add a bit more space between the two plots.
# fig.subplots_adjust(hspace=0.3)
plt.show()
